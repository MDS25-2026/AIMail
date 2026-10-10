package main

import (
	"context"
	"encoding/base64"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/joho/godotenv"
)

// Checked scans accept a measured miss rate (signature-detection.md): on the synthetic scans in
// testdata/marks, Gemma-SEA-LION-v4 4B missed 1 of 12 marked pages. More than that is a regression.
// Clear pages held back are only reported: they lose a cloud transcription, not their text.
const maxMarkedMissed = 1

func TestLiveMarkCheckMissesNoMoreThanMeasured(t *testing.T) {
	_ = godotenv.Load("../.env")
	model := os.Getenv("LOCAL_VISION_MODEL")
	if model == "" {
		t.Skip("LOCAL_VISION_MODEL is not set")
	}
	base := strings.TrimRight(getEnvOrDefault("LOCAL_LLM_URL", defaultLocalLLMURL), "/")
	if resp, err := (&http.Client{Timeout: 2 * time.Second}).Get(base + "/api/version"); err != nil {
		t.Skip("Ollama unreachable — start it: ollama serve")
	} else {
		resp.Body.Close()
	}
	missed := askAll(t, model, "marked", true)
	held := askAll(t, model, "clear", false)
	t.Logf("clear pages held back: %d", held)
	t.Logf("marked pages missed: %d", missed)
	if missed > maxMarkedMissed {
		t.Fatalf("%d marked page(s) would have reached Gemini, more than the measured %d", missed, maxMarkedMissed)
	}
}

// askAll counts the pages in folder whose answer differs from want.
func askAll(t *testing.T, model, folder string, want bool) int {
	t.Helper()
	paths, err := filepath.Glob(filepath.Join("testdata", "marks", folder, "*.png"))
	if err != nil || len(paths) == 0 {
		t.Fatalf("no scans in testdata/marks/%s", folder)
	}
	wrong := 0
	for _, path := range paths {
		raw, err := os.ReadFile(path)
		if err != nil {
			t.Fatal(err)
		}
		found, err := hasMark(context.Background(), model, base64.StdEncoding.EncodeToString(raw))
		if err != nil {
			t.Fatalf("%s: %v", path, err)
		}
		if found != want {
			wrong++
			t.Logf("%s: found=%v, want %v", filepath.Base(path), found, want)
		}
	}
	return wrong
}
