package main

import (
	"testing"

	"google.golang.org/api/gmail/v1"
)

func authHeaders(values ...string) []*gmail.MessagePartHeader {
	headers := make([]*gmail.MessagePartHeader, 0, len(values))
	for _, value := range values {
		headers = append(headers, &gmail.MessagePartHeader{Name: "Authentication-Results", Value: value})
	}
	return headers
}

const (
	googleAllPass = "mx.google.com; dkim=pass header.i=@corp.example header.s=s1; " +
		"spf=pass (google.com: domain of a@corp.example designates 1.2.3.4 as permitted sender) " +
		"smtp.mailfrom=a@corp.example; dmarc=pass (p=REJECT sp=REJECT dis=NONE) header.from=corp.example"
	googleSPFFail = "mx.google.com; spf=fail (google.com: domain does not designate 6.6.6.6) smtp.mailfrom=bank.example"
	forgedAllPass = "attacker.example; dkim=pass; spf=pass; dmarc=pass header.from=bank.example"
)

func TestParseAuthStatusFollowsTheContract(t *testing.T) {
	cases := []struct {
		name    string
		headers []*gmail.MessagePartHeader
		want    string
	}{
		{"dmarc pass", authHeaders(googleAllPass), authPass},
		{"dmarc pass alone", authHeaders("mx.google.com; dmarc=pass header.from=x.example"), authPass},
		{"spf and dkim pass with no dmarc", authHeaders("mx.google.com; dkim=pass; spf=pass"), authPass},
		{"spf pass only", authHeaders("mx.google.com; spf=pass smtp.mailfrom=x.example"), authUnverified},
		{"spf and dkim pass with dmarc none", authHeaders("mx.google.com; dkim=pass; spf=pass; dmarc=none"), authUnverified},
		{"spf fail", authHeaders(googleSPFFail), authSpoofDetected},
		{"dkim fail", authHeaders("mx.google.com; dkim=fail header.i=@bank.example"), authSpoofDetected},
		{"dmarc fail", authHeaders("mx.google.com; dmarc=fail (p=NONE) header.from=bank.example"), authSpoofDetected},
		{"dmarc pass beside a failed dkim", authHeaders("mx.google.com; dkim=fail; dkim=pass; dmarc=pass"), authSpoofDetected},
		{"versioned method and authserv-id", authHeaders("MX.Google.com 1; DKIM/1=FAIL"), authSpoofDetected},
		{"temperror", authHeaders("mx.google.com; spf=temperror; dkim=temperror"), authUnverified},
		{"permerror", authHeaders("mx.google.com; dmarc=permerror"), authUnverified},
		{"neutral and softfail", authHeaders("mx.google.com; spf=softfail; dkim=neutral"), authUnverified},
		{"none", authHeaders("mx.google.com; spf=none; dkim=none; dmarc=none"), authUnverified},
		{"google header with no results", authHeaders("mx.google.com"), authUnverified},
		{"no header", nil, authUnverified},
		{"only another authserv-id", authHeaders(forgedAllPass), authUnverified},
		{"fail inside a comment", authHeaders("mx.google.com; spf=pass (spf=fail) smtp.mailfrom=x; dkim=pass"), authPass},
		{"fail inside a property", authHeaders("mx.google.com; dmarc=pass reason=dkim=fail"), authPass},
		{"forged pass above google's fail", authHeaders(forgedAllPass, googleSPFFail), authSpoofDetected},
		{"forged pass below google's fail", authHeaders(googleSPFFail, forgedAllPass), authSpoofDetected},
		{"forged google header below the real one", authHeaders(googleSPFFail, "mx.google.com; dmarc=pass"), authSpoofDetected},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			if got := parseAuthStatus(tc.headers); got != tc.want {
				t.Fatalf("want %q, got %q", tc.want, got)
			}
		})
	}
}
