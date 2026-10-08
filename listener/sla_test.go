package main

import (
	"testing"
	"time"
)

// fixed is a Monday, 09:00 UTC — a realistic "received at" anchor for tests.
var fixed = time.Date(2024, time.March, 11, 9, 0, 0, 0, time.UTC)

func TestClassifySLA(t *testing.T) {
	tests := []struct {
		name       string
		subject    string
		body       string
		receivedAt time.Time
		want       SLAPriority
	}{
		// ---- LOW: newsletter / automated patterns ----
		{
			name:    "subject prefix [Newsletter]",
			subject: "[Newsletter] Weekly digest",
			body:    "Read our latest updates.",
			want:    SLALow,
		},
		{
			name:    "subject prefix [Automated]",
			subject: "[Automated] Daily report",
			body:    "Your report is ready.",
			want:    SLALow,
		},
		{
			name:    "subject prefix [No-Reply]",
			subject: "[No-Reply] System alert",
			body:    "Something happened.",
			want:    SLALow,
		},
		{
			name:    "subject prefix [Digest]",
			subject: "[Digest] Monthly highlights",
			body:    "Here are the highlights.",
			want:    SLALow,
		},
		{
			name:    "subject prefix [Notification]",
			subject: "[Notification] You have a new comment",
			body:    "Someone commented.",
			want:    SLALow,
		},
		{
			name:    "subject contains unsubscribe",
			subject: "How to unsubscribe from this list",
			body:    "Please follow the link.",
			want:    SLALow,
		},
		{
			name:    "subject contains newsletter (word)",
			subject: "Our quarterly newsletter is here",
			body:    "Read all about it.",
			want:    SLALow,
		},
		{
			name:    "body contains to unsubscribe",
			subject: "Updates from us",
			body:    "Click here to unsubscribe from future emails.",
			want:    SLALow,
		},
		// ---- CRITICAL: urgent keyword ----
		{
			name:    "ASAP keyword",
			subject: "Need sign-off ASAP",
			body:    "Please review.",
			want:    SLACritical,
		},
		{
			name:    "urgent keyword",
			subject: "Urgent: server is down",
			body:    "Fix required.",
			want:    SLACritical,
		},
		{
			name:    "by EOD",
			subject: "Approval needed",
			body:    "Please confirm by EOD.",
			want:    SLACritical,
		},
		{
			name:    "by end of day",
			subject: "Report",
			body:    "I need this by end of day.",
			want:    SLACritical,
		},
		{
			name:    "within 24 hours",
			subject: "Action required",
			body:    "Respond within 24 hours.",
			want:    SLACritical,
		},
		{
			name:    "as soon as possible",
			subject: "Fix",
			body:    "Please fix this as soon as possible.",
			want:    SLACritical,
		},
		{
			name:    "ISO date same day — CRITICAL",
			subject: "Meeting today",
			body:    "Please join by 2024-03-11.",
			want:    SLACritical,
		},
		{
			name:    "ISO date next day — CRITICAL (within 1)",
			subject: "Deadline",
			body:    "Submit by 2024-03-12.",
			want:    SLACritical,
		},
		// ---- HIGH: 2-3 day window ----
		{
			name:    "by tomorrow keyword",
			subject: "Review needed",
			body:    "Get it done by tomorrow.",
			want:    SLAHigh,
		},
		{
			name:    "within 3 days keyword",
			subject: "Action item",
			body:    "Please respond within 3 days.",
			want:    SLAHigh,
		},
		{
			name:    "ISO date within 3 days — HIGH",
			subject: "Deadline",
			body:    "Deliver by 2024-03-13.", // +2 days
			want:    SLAHigh,
		},
		{
			name:    "natural date DD Month — HIGH",
			subject: "Report due",
			body:    "Please submit by 14 March.",
			want:    SLAHigh,
		},
		// ---- MEDIUM: 4-7 day window ----
		{
			name:    "this week keyword",
			subject: "Team update",
			body:    "Let me know this week.",
			want:    SLAMedium,
		},
		{
			name:    "end of week keyword",
			subject: "Feedback",
			body:    "Please send feedback by end of week.",
			want:    SLAMedium,
		},
		{
			name:    "within a week",
			subject: "Response",
			body:    "Reply within a week.",
			want:    SLAMedium,
		},
		{
			name:    "ISO date within 7 days — MEDIUM",
			subject: "Deadline",
			body:    "Due by 2024-03-17.", // +6 days
			want:    SLAMedium,
		},
		{
			name:    "Month DD format — MEDIUM",
			subject: "Conference abstract",
			body:    "Submit by March 16, 2024.",
			want:    SLAMedium,
		},
		// ---- UNSET: no rule matches ----
		{
			name:    "plain email, no urgency",
			subject: "Catching up",
			body:    "Hope you are well. Let us grab coffee sometime.",
			want:    SLAUnset,
		},
		{
			name:    "date in the past — no rule",
			subject: "Old deadline",
			body:    "The deadline was 2024-02-01.",
			want:    SLAUnset,
		},
		{
			name:    "date far in the future — no rule",
			subject: "Annual review",
			body:    "Your review is scheduled for 2024-06-15.",
			want:    SLAUnset,
		},
		{
			name:    "casual greeting mentioning today must NOT trigger CRITICAL",
			subject: "Hello there",
			body:    "Hope you are having a wonderful day today! Talk soon.",
			want:    SLAUnset,
		},
		{
			name:    "casual question mentioning today must NOT trigger CRITICAL",
			subject: "Lunch today?",
			body:    "Are you free for lunch today?",
			want:    SLAUnset,
		},
		{
			name:    "Malay urgency keyword 'segera'",
			subject: "Tindakan segera diperlukan",
			body:    "Sila sahkan dokumen ini dengan segera.",
			want:    SLACritical,
		},
		{
			name:    "Chinese urgency keyword '加急'",
			subject: "加急：系统故障处理",
			body:    "请立即查看生产环境日志。",
			want:    SLACritical,
		},
		{
			name:    "Malay deadline 'esok' -> HIGH",
			subject: "Laporan jualan",
			body:    "Sila hantar laporan ini selewat-lewatnya esok.",
			want:    SLAHigh,
		},
		{
			name:    "Chinese deadline '周末前' -> MEDIUM",
			subject: "项目周报",
			body:    "请在周末前完成评审工作。",
			want:    SLAMedium,
		},
		// ---- Priority ordering: LOW beats urgent-looking subject ----
		{
			name:    "newsletter with urgent word in body — LOW wins",
			subject: "[Newsletter] Urgent offers inside",
			body:    "Act now! To unsubscribe click here.",
			want:    SLALow,
		},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			at := tc.receivedAt
			if at.IsZero() {
				at = fixed
			}
			got := ClassifySLA(tc.subject, tc.body, at)
			if got != tc.want {
				t.Errorf("ClassifySLA(%q, %q) = %q, want %q", tc.subject, tc.body, got, tc.want)
			}
		})
	}
}
