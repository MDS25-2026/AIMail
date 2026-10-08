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

// Short, so switching to Private mode reaches the listener within a minute without a lookup per image.
const providerCacheTTL = 30 * time.Second

// Why the images of a message were not sent to Gemini.
const (
	reasonPrivateMode     = "private_mode"
	reasonOwnerUnknown    = "owner_unknown"
	reasonLookupFailed    = "provider_lookup_failed"
	reasonUnknownProvider = "unknown_provider"
)

type cachedProvider struct {
	provider  string
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
	provider, err := draftProvider(ctx, ownerID)
	if err != nil {
		log.Printf("could not read the provider of user %s, not sending images to OCR: %v", ownerID, err)
		return reasonLookupFailed
	}
	switch provider {
	case providerGemini:
		return ""
	case providerLocal:
		return reasonPrivateMode
	}
	return reasonUnknownProvider
}

// draftProvider caches successful lookups only, so a failure is asked again on the next message.
func draftProvider(ctx context.Context, ownerID string) (string, error) {
	providerCache.Lock()
	cached, isCached := providerCache.byOwner[ownerID]
	providerCache.Unlock()
	if isCached && time.Since(cached.fetchedAt) < providerCacheTTL {
		return cached.provider, nil
	}
	provider, err := fetchDraftProvider(ctx, ownerID)
	if err != nil {
		return "", err
	}
	providerCache.Lock()
	providerCache.byOwner[ownerID] = cachedProvider{provider: provider, fetchedAt: time.Now()}
	providerCache.Unlock()
	return provider, nil
}

// fetchDraftProvider reads the owner's choice; no row means they never chose, which is the column default.
func fetchDraftProvider(ctx context.Context, ownerID string) (string, error) {
	body, err := supabaseGet(ctx, "user_preferences", "select=draft_provider&user_id=eq."+url.QueryEscape(ownerID))
	if err != nil {
		return "", err
	}
	var rows []struct {
		DraftProvider string `json:"draft_provider"`
	}
	if err := json.Unmarshal(body, &rows); err != nil {
		return "", fmt.Errorf("decode user_preferences: %w", err)
	}
	if len(rows) == 0 {
		return providerGemini, nil
	}
	return rows[0].DraftProvider, nil
}
