package main

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"
)

func TestTheServiceRefusesToStartWithoutItsPubSubSettings(t *testing.T) {
	t.Setenv(envGCPProject, "proj")
	t.Setenv(envPubSubTopic, "")
	t.Setenv(envPubSubSubscription, " ")
	_, err := loadPubSubConfig()
	if err == nil || !strings.Contains(err.Error(), envPubSubTopic) || !strings.Contains(err.Error(), envPubSubSubscription) {
		t.Fatalf("want both missing settings named, got %v", err)
	}
}

func TestTheWatchTopicIsBuiltFromTheSettings(t *testing.T) {
	t.Setenv(envGCPProject, "proj")
	t.Setenv(envPubSubTopic, "gmail-notifications")
	t.Setenv(envPubSubSubscription, "gmail-notifications-sub")
	cfg, err := loadPubSubConfig()
	if err != nil || cfg.topicPath() != "projects/proj/topics/gmail-notifications" {
		t.Fatalf("got %q, %v", cfg.topicPath(), err)
	}
}

func probe(t *testing.T, path string) *httptest.ResponseRecorder {
	t.Helper()
	recorder := httptest.NewRecorder()
	healthHandler().ServeHTTP(recorder, httptest.NewRequest(http.MethodGet, path, nil))
	return recorder
}

func TestLivenessAnswersWithoutCheckingDependencies(t *testing.T) {
	t.Setenv("PRESIDIO_ANALYZER_URL", "http://127.0.0.1:1/analyze")
	if got := probe(t, "/healthz"); got.Code != http.StatusOK {
		t.Fatalf("got %d", got.Code)
	}
}

func TestReadinessFailsWhilePresidioIsDown(t *testing.T) {
	withSupabase(t, func(w http.ResponseWriter, _ *http.Request) { w.Write([]byte(`[]`)) })
	t.Setenv("PRESIDIO_ANALYZER_URL", "http://127.0.0.1:1/analyze")
	got := probe(t, "/readyz")
	if got.Code != http.StatusServiceUnavailable || !strings.Contains(got.Body.String(), `"presidio":false`) {
		t.Fatalf("got %d %s", got.Code, got.Body.String())
	}
}

func TestReadinessReportsTheLastReceiveWithoutJudgingIt(t *testing.T) {
	withSupabase(t, func(w http.ResponseWriter, _ *http.Request) { w.Write([]byte(`[]`)) })
	fakePresidio(t)
	lastReceive.Store(0)
	if got := probe(t, "/readyz"); got.Code != http.StatusOK ||
		!strings.Contains(got.Body.String(), `"seconds_since_last_receive":null`) {
		t.Fatalf("got %d %s", got.Code, got.Body.String())
	}
	lastReceive.Store(time.Now().Add(-90 * time.Second).UnixNano())
	t.Cleanup(func() { lastReceive.Store(0) })
	if got := probe(t, "/readyz"); got.Code != http.StatusOK ||
		!strings.Contains(got.Body.String(), `"seconds_since_last_receive":90`) {
		t.Fatalf("a quiet inbox is still ready: %d %s", got.Code, got.Body.String())
	}
}

func TestReadinessFailsWhenSupabaseIsUnreachable(t *testing.T) {
	withSupabase(t, func(w http.ResponseWriter, _ *http.Request) { w.WriteHeader(http.StatusBadGateway) })
	fakePresidio(t)
	if got := probe(t, "/readyz"); got.Code != http.StatusServiceUnavailable {
		t.Fatalf("got %d", got.Code)
	}
}
