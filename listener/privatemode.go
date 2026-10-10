package main

// Private mode (specs/features/local-model.md) is a user's choice to keep their email inside the
// company. OCR is the one listener step that reaches Gemini, so it asks the owner's choice first and
// fails closed: when the choice cannot be known, the redacted images are not sent.

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net/url"
	"sync"
	"time"
)

// Values of user_preferences.draft_provider (migration 0022); the backend's DraftProvider mirrors them.
const (
	providerGemini = "gemini"
	providerLocal  = "local"
)

// Values of user_preferences.scan_reading (migration 0036): scans read on this machine only, or
// checked for signatures, faces and stamps by the local vision model and the clear ones sent on.
const (
	scanReadingLocal   = "local"
	scanReadingChecked = "checked"
)

// Short, so switching to Private mode reaches the listener within a minute without a lookup per image.
const providerCacheTTL = 30 * time.Second

// Why the images of a message were not sent to Gemini.
const (
	reasonPrivateMode     = "private_mode"
	reasonOwnerUnknown    = "owner_unknown"
	reasonLookupFailed    = "provider_lookup_failed"
	reasonUnknownProvider = "unknown_provider"
	reasonScansLocal      = "scans_local"
)

type preferences struct {
	provider    string
	scanReading string
}

type cachedProvider struct {
	preferences
	fetchedAt time.Time
}

var providerCache = struct {
	sync.Mutex
	byOwner map[string]cachedProvider
}{byOwner: map[string]cachedProvider{}}

// cloudOCRRefusal is why this owner's images must not reach Gemini, or "" when they may. The
// token.json mailbox has no owner whose choice could be read, so it is refused too.
func cloudOCRRefusal(ctx context.Context, ownerID string) string {
	if ownerID == "" {
		return reasonOwnerUnknown
	}
	prefs, err := ownerPreferences(ctx, ownerID)
	if err != nil {
		log.Printf("could not read the provider of user %s, not sending images to OCR: %v", ownerID, err)
		return reasonLookupFailed
	}
	switch prefs.provider {
	case providerLocal:
		return reasonPrivateMode
	case providerGemini:
		return scanRefusal(prefs.scanReading)
	}
	return reasonUnknownProvider
}

// scanRefusal keeps scans local unless the owner chose the checked mode; an unknown value is local.
func scanRefusal(scanReading string) string {
	if scanReading == scanReadingChecked {
		return ""
	}
	return reasonScansLocal
}

// isOwnersChoice tells a refusal the owner asked for from one forced by a missing or failed lookup.
func isOwnersChoice(reason string) bool {
	return reason == reasonPrivateMode || reason == reasonScansLocal
}

// ownerPreferences caches successful lookups only, so a failure is asked again on the next message.
func ownerPreferences(ctx context.Context, ownerID string) (preferences, error) {
	providerCache.Lock()
	cached, isCached := providerCache.byOwner[ownerID]
	providerCache.Unlock()
	if isCached && time.Since(cached.fetchedAt) < providerCacheTTL {
		return cached.preferences, nil
	}
	prefs, err := fetchPreferences(ctx, ownerID)
	if err != nil {
		return preferences{}, err
	}
	providerCache.Lock()
	providerCache.byOwner[ownerID] = cachedProvider{preferences: prefs, fetchedAt: time.Now()}
	providerCache.Unlock()
	return prefs, nil
}

// fetchPreferences reads the owner's choices; no row means they never chose: the column defaults.
func fetchPreferences(ctx context.Context, ownerID string) (preferences, error) {
	body, err := supabaseGet(ctx, "user_preferences",
		"select=draft_provider,scan_reading&user_id=eq."+url.QueryEscape(ownerID))
	if err != nil {
		return preferences{}, err
	}
	var rows []struct {
		DraftProvider string `json:"draft_provider"`
		ScanReading   string `json:"scan_reading"`
	}
	if err := json.Unmarshal(body, &rows); err != nil {
		return preferences{}, fmt.Errorf("decode user_preferences: %w", err)
	}
	if len(rows) == 0 {
		return preferences{provider: providerGemini, scanReading: scanReadingLocal}, nil
	}
	return preferences{provider: rows[0].DraftProvider, scanReading: rows[0].ScanReading}, nil
}
