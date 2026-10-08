package main

// Health endpoints for whatever runs the service: /healthz says the process is up, /readyz whether
// it can do its job. Both answer with booleans and numbers only, never an id or an error's text.

import (
	"context"
	"encoding/json"
	"errors"
	"log"
	"net/http"
	"sync/atomic"
	"time"
)

const (
	healthAddrEnv         = "LISTENER_HEALTH_ADDR"
	defaultHealthAddr     = "127.0.0.1:8095"
	healthShutdownTimeout = 5 * time.Second
	readinessTimeout      = 3 * time.Second
)

// lastReceive is when the last Pub/Sub notification arrived, in Unix nanoseconds; 0 until the first.
var lastReceive atomic.Int64

func markReceived() {
	lastReceive.Store(time.Now().UnixNano())
}

// readiness is not gated on lastReceive: a quiet inbox is normal, so the age is reported, not judged.
type readiness struct {
	Supabase                bool   `json:"supabase"`
	Presidio                bool   `json:"presidio"`
	SecondsSinceLastReceive *int64 `json:"seconds_since_last_receive"` // null until the first notification
}

func (r readiness) isReady() bool {
	return r.Supabase && r.Presidio
}

func checkReadiness(ctx context.Context) readiness {
	ctx, cancel := context.WithTimeout(ctx, readinessTimeout)
	defer cancel()
	_, supabaseErr := supabaseGet(ctx, "messages", "select=gmail_message_id&limit=1")
	return readiness{Supabase: supabaseErr == nil, Presidio: presidioHealthy(ctx), SecondsSinceLastReceive: secondsSinceReceive()}
}

func secondsSinceReceive() *int64 {
	last := lastReceive.Load()
	if last == 0 {
		return nil
	}
	seconds := int64(time.Since(time.Unix(0, last)).Seconds())
	return &seconds
}

func healthHandler() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /healthz", func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", jsonContentType)
		w.Write([]byte(aliveBody))
	})
	mux.HandleFunc("GET /readyz", serveReadiness)
	return mux
}

const (
	jsonContentType = "application/json"
	aliveBody       = `{"ok":true}`
)

func serveReadiness(w http.ResponseWriter, r *http.Request) {
	state := checkReadiness(r.Context())
	status := http.StatusServiceUnavailable
	if state.isReady() {
		status = http.StatusOK
	}
	w.Header().Set("Content-Type", jsonContentType)
	w.WriteHeader(status)
	if err := json.NewEncoder(w).Encode(state); err != nil {
		log.Printf("readiness response not written: %v", err)
	}
}

// startHealthServer serves until shutdown. A failure to bind is logged, not fatal: ingesting mail
// matters more than answering probes, and a probe that cannot connect already reports the problem.
func startHealthServer(addr string) *http.Server {
	server := &http.Server{Addr: addr, Handler: healthHandler(), ReadHeaderTimeout: readinessTimeout}
	go func() {
		if err := server.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
			log.Printf("health server on %s stopped: %v", addr, err)
		}
	}()
	log.Printf("health endpoints on http://%s/healthz and /readyz", addr)
	return server
}

func stopHealthServer(server *http.Server) {
	ctx, cancel := context.WithTimeout(context.Background(), healthShutdownTimeout)
	defer cancel()
	if err := server.Shutdown(ctx); err != nil {
		log.Printf("health server did not stop cleanly: %v", err)
	}
}
