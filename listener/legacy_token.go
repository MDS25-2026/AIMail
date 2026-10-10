package main

// The original token.json mailbox (per-user-mailboxes.md). It is optional: connected users need
// neither file, so a service started without them, or with no terminal to sign in on, runs without it.

import (
	"context"
	"crypto/rand"
	"encoding/json"
	"errors"
	"fmt"
	"log"
	"os"

	"golang.org/x/oauth2"
	"golang.org/x/oauth2/google"
	"google.golang.org/api/gmail/v1"
	"google.golang.org/api/option"
)

const (
	credentialsFile = "credentials.json"
	tokenFile       = "token.json"
	pubsubScope     = "https://www.googleapis.com/auth/pubsub"
)

var errNoTerminal = errors.New("no token.json and no terminal to sign in on")

// legacyTokenSource is the token.json account, or nil when this run goes without it.
func legacyTokenSource(ctx context.Context) oauth2.TokenSource {
	config, err := legacyOAuthConfig()
	if err != nil {
		log.Printf("token.json mailbox skipped: %v", err)
		return nil
	}
	tok, err := legacyToken(ctx, config)
	if err != nil {
		log.Printf("token.json mailbox skipped: %v", err)
		return nil
	}
	return config.TokenSource(ctx, tok)
}

func legacyOAuthConfig() (*oauth2.Config, error) {
	raw, err := os.ReadFile(credentialsFile)
	if err != nil {
		return nil, fmt.Errorf("read %s: %w", credentialsFile, err)
	}
	config, err := google.ConfigFromJSON(raw, gmail.GmailReadonlyScope, gmail.GmailSendScope, pubsubScope)
	if err != nil {
		return nil, fmt.Errorf("parse %s: %w", credentialsFile, err)
	}
	return config, nil
}

// legacyToken reads token.json, asking for consent only when someone is at a terminal to give it;
// a service would otherwise wait on stdin forever.
func legacyToken(ctx context.Context, config *oauth2.Config) (*oauth2.Token, error) {
	tok, err := tokenFromFile(tokenFile)
	if err == nil {
		return tok, nil
	}
	if !isTerminal(os.Stdin) {
		return nil, errNoTerminal
	}
	tok, err = tokenFromWeb(ctx, config)
	if err != nil {
		return nil, err
	}
	saveToken(tokenFile, tok)
	return tok, nil
}

func isTerminal(file *os.File) bool {
	info, err := file.Stat()
	return err == nil && info.Mode()&os.ModeCharDevice != 0
}

// tokenFromWeb signs in with a pasted code. The code comes back by hand, not by redirect, so state
// cannot be checked here; PKCE is what protects it: a code copied by anyone else is useless without
// this run's verifier. The state is still random, never a fixed string a forged request could reuse.
func tokenFromWeb(ctx context.Context, config *oauth2.Config) (*oauth2.Token, error) {
	verifier := oauth2.GenerateVerifier()
	authURL := config.AuthCodeURL(rand.Text(), oauth2.AccessTypeOffline, oauth2.S256ChallengeOption(verifier))
	fmt.Printf("Go to the following link in your browser then type the authorization code: \n%v\n\nCode: ", authURL)
	var authCode string
	if _, err := fmt.Scan(&authCode); err != nil {
		return nil, fmt.Errorf("read authorization code: %w", err)
	}
	tok, err := config.Exchange(ctx, authCode, oauth2.VerifierOption(verifier))
	if err != nil {
		return nil, fmt.Errorf("exchange authorization code: %w", err)
	}
	return tok, nil
}

func tokenFromFile(file string) (*oauth2.Token, error) {
	f, err := os.Open(file)
	if err != nil {
		return nil, err
	}
	defer f.Close()
	tok := &oauth2.Token{}
	err = json.NewDecoder(f).Decode(tok)
	return tok, err
}

func saveToken(path string, token *oauth2.Token) {
	fmt.Printf("Saving credential file to: %s\n", path)
	f, err := os.OpenFile(path, os.O_RDWR|os.O_CREATE|os.O_TRUNC, 0600)
	if err != nil {
		log.Printf("could not save %s, consent will be asked again next start: %v", path, err)
		return
	}
	defer f.Close()
	if err := json.NewEncoder(f).Encode(token); err != nil {
		log.Printf("could not write %s: %v", path, err)
	}
}

// pubsubOptions authenticates Pub/Sub as the token.json account while it exists; without it the
// client uses Application Default Credentials, the service account a deployment provides.
func pubsubOptions(legacy oauth2.TokenSource) []option.ClientOption {
	if legacy == nil {
		log.Printf("Pub/Sub authenticates with Application Default Credentials")
		return nil
	}
	return []option.ClientOption{option.WithTokenSource(legacy)}
}

// startLegacyMailbox watches the token.json mailbox when this run has its token.
func startLegacyMailbox(ctx context.Context, legacy oauth2.TokenSource) {
	if legacy == nil {
		return
	}
	srv, err := gmail.NewService(ctx, option.WithTokenSource(legacy))
	if err != nil {
		log.Printf("token.json mailbox not started: %v", err)
		return
	}
	startTokenFileMailbox(ctx, srv)
}
