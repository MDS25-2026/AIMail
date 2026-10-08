package main

import (
	"regexp"
	"strings"
	"time"
)

// SLAPriority is the deterministic priority assigned by the rules engine at ingestion time.
// When a rule fires it overrides the AI classifier; SLAUnset lets the AI decide.
type SLAPriority string

const (
	SLACritical SLAPriority = "CRITICAL" // deadline within 24 h, or urgent keyword
	SLAHigh     SLAPriority = "HIGH"     // deadline within 3 days
	SLAMedium   SLAPriority = "MEDIUM"   // deadline within 7 days
	SLALow      SLAPriority = "LOW"      // newsletter / automated / no-reply
	SLAUnset    SLAPriority = ""         // no rule fired; let the AI decide
)

// ---------------------------------------------------------------------------
// Rule 1 — Newsletter / Automated (LOW)
// ---------------------------------------------------------------------------

var (
	// Subject prefixes that signal automated mail.
	lowSubjectPrefixRe = regexp.MustCompile(
		`(?i)^\s*\[(newsletter|automated|no.?reply|digest|notification)\]`,
	)
	// Words anywhere in the subject.
	lowSubjectWordRe = regexp.MustCompile(
		`(?i)\b(unsubscribe|newsletter|digest)\b`,
	)
	// Canonical body phrase for bulk mail.
	lowBodyRe = regexp.MustCompile(`(?i)\bto unsubscribe\b`)
)

func isLow(subject, body string) bool {
	return lowSubjectPrefixRe.MatchString(subject) ||
		lowSubjectWordRe.MatchString(subject) ||
		lowBodyRe.MatchString(body)
}

// ---------------------------------------------------------------------------
// Rule 2 — CRITICAL (24 h)
// ---------------------------------------------------------------------------

// Explicit actionable urgency. Avoid standalone casual "today" (e.g. "how are you today")
// by requiring actionable contexts: "due today", "by today", "needed today", "finish today",
// "sebelum hari ini", or explicit markers (ASAP, EOD, COB, 24h, segera, 紧急, 今日内).
// English and Malay phrases use ASCII word boundaries (\b).
var criticalPhraseRe = regexp.MustCompile(
	`(?i)\b(` +
		`by end of day|by eod|by cob|end of day|end of business|` +
		`within 24 hours?|within the hour|` +
		`asap|as soon as possible|action required immediately|urgent(?:ly)?|` +
		`(?:due|by|needed|required|finish|submit|respond|reply|complete)\s+(?:by\s+)?today|` +
		`segera|tindakan segera|dalam tempoh 24 jam|hari ini juga` +
		`)\b`,
)

// Chinese / CJK urgency phrases without \b because Go RE2's \b treats non-ASCII as non-word chars.
var criticalCjkRe = regexp.MustCompile(
	`紧急|加急|立即|今日内|24小时内`,
)

// ---------------------------------------------------------------------------
// Rule 3 — HIGH (3 days)
// ---------------------------------------------------------------------------

var highPhraseRe = regexp.MustCompile(
	`(?i)\b(` +
		`by tomorrow|next (?:business )?day|within [23] days?|in [23] days?|` +
		`esok|dalam masa [23] hari` +
		`)\b`,
)

var highCjkRe = regexp.MustCompile(
	`明天|明日|两三天内|3天内`,
)

// ---------------------------------------------------------------------------
// Rule 4 — MEDIUM (7 days)
// ---------------------------------------------------------------------------

var mediumPhraseRe = regexp.MustCompile(
	`(?i)\b(` +
		`this week|end of (?:the )?week|by (?:end of )?friday|within (?:a|1|one|7) week|` +
		`in (?:a|1|one|7) week|within [4-7] days?|in [4-7] days?|` +
		`minggu ini|hujung minggu ini|dalam tempoh seminggu` +
		`)\b`,
)

var mediumCjkRe = regexp.MustCompile(
	`本周|本周内|周末前|一周内`,
)

// ---------------------------------------------------------------------------
// Date extraction
// ---------------------------------------------------------------------------

// ISO and common numeric formats: YYYY-MM-DD, DD/MM/YYYY, MM/DD/YYYY.
var isoDateRe = regexp.MustCompile(
	`\b(\d{4})-(\d{2})-(\d{2})\b` + // YYYY-MM-DD
		`|\b(\d{2})/(\d{2})/(\d{4})\b`, // DD/MM/YYYY or MM/DD/YYYY (disambiguated below)
)

// Month names for natural-language dates.
var monthNames = map[string]time.Month{
	"january": time.January, "february": time.February, "march": time.March,
	"april": time.April, "may": time.May, "june": time.June,
	"july": time.July, "august": time.August, "september": time.September,
	"october": time.October, "november": time.November, "december": time.December,
	"jan": time.January, "feb": time.February, "mar": time.March,
	"apr": time.April, "jun": time.June,
	"jul": time.July, "aug": time.August, "sep": time.September,
	"oct": time.October, "nov": time.November, "dec": time.December,
}

// monthNameList is a | -joined list of all month name variants for the regex.
var monthNamePattern = buildMonthPattern()

func buildMonthPattern() string {
	// longest first so "january" beats "jan"
	long := []string{
		"january", "february", "march", "april", "may", "june",
		"july", "august", "september", "october", "november", "december",
	}
	short := []string{"jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep", "oct", "nov", "dec"}
	return strings.Join(append(long, short...), "|")
}

// naturalDateRe matches:
//   - "January 2, 2006" / "January 2"
//   - "2 January 2006" / "2 January"
var naturalDateRe = regexp.MustCompile(
	`(?i)\b(` + monthNamePattern + `)\s+(\d{1,2})(?:st|nd|rd|th)?,?\s*(\d{4})?\b` +
		`|\b(\d{1,2})(?:st|nd|rd|th)?\s+(` + monthNamePattern + `)(?:\s+(\d{4}))?\b`,
)

// parsedDates extracts all candidate dates from text and returns them as time.Time values
// (UTC, time zeroed to midnight). Year omission is filled with the year of receivedAt.
func parsedDates(text string, receivedAt time.Time) []time.Time {
	year := receivedAt.Year()
	var dates []time.Time

	// ISO / numeric formats
	for _, m := range isoDateRe.FindAllStringSubmatch(text, -1) {
		var t time.Time
		var err error
		if m[1] != "" {
			// YYYY-MM-DD
			t, err = time.Parse("2006-01-02", m[0])
		} else {
			// DD/MM/YYYY — try both interpretations and keep the one that makes a valid date.
			// DD/MM/YYYY
			t, err = time.Parse("02/01/2006", m[0])
			if err != nil {
				// MM/DD/YYYY
				t, err = time.Parse("01/02/2006", m[0])
			}
		}
		if err == nil {
			dates = append(dates, t.UTC())
		}
	}

	// Natural language dates
	for _, m := range naturalDateRe.FindAllStringSubmatch(text, -1) {
		var monthStr, dayStr, yearStr string
		if m[1] != "" {
			// "Month DD [YYYY]"
			monthStr = strings.ToLower(m[1])
			dayStr = m[2]
			yearStr = m[3]
		} else {
			// "DD Month [YYYY]"
			dayStr = m[4]
			monthStr = strings.ToLower(m[5])
			yearStr = m[6]
		}
		month, ok := monthNames[monthStr]
		if !ok {
			continue
		}
		day := atoi(dayStr)
		if day < 1 || day > 31 {
			continue
		}
		y := year
		if yearStr != "" {
			y = atoi(yearStr)
		}
		t := time.Date(y, month, day, 0, 0, 0, 0, time.UTC)
		dates = append(dates, t)
	}

	return dates
}

// atoi converts a string to int, returning 0 on error.
func atoi(s string) int {
	n := 0
	for _, c := range s {
		if c < '0' || c > '9' {
			return 0
		}
		n = n*10 + int(c-'0')
	}
	return n
}

// daysBetween returns the calendar-day difference (date - base), truncated to midnight UTC.
// Negative means date is in the past.
func daysBetween(date, base time.Time) int {
	d := date.UTC().Truncate(24 * time.Hour)
	b := base.UTC().Truncate(24 * time.Hour)
	return int(d.Sub(b) / (24 * time.Hour))
}

// ---------------------------------------------------------------------------
// Main entry point
// ---------------------------------------------------------------------------

// ClassifySLA applies the deterministic priority rules to an email's subject and body.
// Rules are tested in priority order; the first match wins. SLAUnset means no rule fired.
func ClassifySLA(subject, body string, receivedAt time.Time) SLAPriority {
	combined := subject + " " + body

	// Rule 1: Newsletter / Automated → LOW (checked first so bulk mail is never escalated)
	if isLow(subject, body) {
		return SLALow
	}

	// Rules 2–4 use both phrase matching and explicit date detection.
	dates := parsedDates(combined, receivedAt)

	// Rule 2: CRITICAL — within 24 h or urgent keyword
	if criticalPhraseRe.MatchString(combined) || criticalCjkRe.MatchString(combined) {
		return SLACritical
	}
	for _, d := range dates {
		if n := daysBetween(d, receivedAt); n >= 0 && n <= 1 {
			return SLACritical
		}
	}

	// Rule 3: HIGH — within 3 days or tomorrow-class phrase
	if highPhraseRe.MatchString(combined) || highCjkRe.MatchString(combined) {
		return SLAHigh
	}
	for _, d := range dates {
		if n := daysBetween(d, receivedAt); n >= 0 && n <= 3 {
			return SLAHigh
		}
	}

	// Rule 4: MEDIUM — within 7 days or "this week" phrase
	if mediumPhraseRe.MatchString(combined) || mediumCjkRe.MatchString(combined) {
		return SLAMedium
	}
	for _, d := range dates {
		if n := daysBetween(d, receivedAt); n >= 0 && n <= 7 {
			return SLAMedium
		}
	}

	return SLAUnset
}
