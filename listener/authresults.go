package main

// Sender verification (specs/context/backbone-contracts.md). Only the Authentication-Results header
// Google's own server added counts: a sender can write any header it likes, including one claiming
// every check passed, so a header from another authserv-id is ignored and unknown never reads as pass.

import (
	"regexp"
	"slices"
	"strings"

	"google.golang.org/api/gmail/v1"
)

// Sender check results; the backend's AuthStatus enum mirrors them (migration 0024).
const (
	authPass          = "pass"
	authSpoofDetected = "spoof_detected"
	authUnverified    = "unverified"
)

const (
	authResultsHeader = "Authentication-Results"
	googleAuthServID  = "mx.google.com"
	methodSPF         = "spf"
	methodDKIM        = "dkim"
	methodDMARC       = "dmarc"
	resultPass        = "pass"
	resultFail        = "fail"
)

// RFC 8601 comments may hold any text, "spf=fail" included, so they are removed before parsing.
var authComment = regexp.MustCompile(`\([^)]*\)`)

// authResults is each method's results in one header; a method can repeat (two DKIM signatures).
type authResults map[string][]string

// parseAuthStatus reads the topmost Authentication-Results header written by mx.google.com.
func parseAuthStatus(headers []*gmail.MessagePartHeader) string {
	results, isFound := googleAuthResults(headers)
	if !isFound {
		return authUnverified
	}
	return results.verdict()
}

// googleAuthResults finds the topmost header from Google's server: Gmail prepends its own, so one
// the sender wrote always sits below it.
func googleAuthResults(headers []*gmail.MessagePartHeader) (authResults, bool) {
	for _, header := range headers {
		if !strings.EqualFold(header.Name, authResultsHeader) {
			continue
		}
		segments := strings.Split(authComment.ReplaceAllString(header.Value, ""), ";")
		// The authserv-id may carry a version after it ("mx.google.com 1"), so only its first token counts.
		if strings.EqualFold(firstToken(segments[0]), googleAuthServID) {
			return parseResults(segments[1:]), true
		}
	}
	return nil, false
}

// parseResults reads only the "method=result" that starts each segment, so a property after it
// (reason=..., header.from=...) is never mistaken for a result.
func parseResults(segments []string) authResults {
	results := authResults{}
	for _, segment := range segments {
		method, result, isPair := strings.Cut(firstToken(segment), "=")
		if !isPair {
			continue
		}
		method, _, _ = strings.Cut(strings.ToLower(method), "/") // "dkim/1" is dkim, version 1
		results[method] = append(results[method], strings.ToLower(result))
	}
	return results
}

// verdict checks failures first: a DMARC pass beside a failed DKIM signature is still a spoof.
func (r authResults) verdict() string {
	for _, method := range []string{methodSPF, methodDKIM, methodDMARC} {
		if slices.Contains(r[method], resultFail) {
			return authSpoofDetected
		}
	}
	if slices.Contains(r[methodDMARC], resultPass) {
		return authPass
	}
	isBothPassed := slices.Contains(r[methodSPF], resultPass) && slices.Contains(r[methodDKIM], resultPass)
	if len(r[methodDMARC]) == 0 && isBothPassed {
		return authPass
	}
	return authUnverified
}

func firstToken(text string) string {
	fields := strings.Fields(text)
	if len(fields) == 0 {
		return ""
	}
	return fields[0]
}
