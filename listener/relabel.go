package main

import (
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"log"
	"net/url"
	"time"

	"google.golang.org/api/gmail/v1"
)

// The headers isAutomated reads; a metadata read returns only these and the labels, never the body.
var automatedHeaders = []string{"List-Id", "List-Unsubscribe", "Precedence", "Auto-Submitted", "Return-Path", "From"}

type relabelRow struct {
	ID             string `json:"id"`
	GmailMessageID string `json:"gmail_message_id"`
	IsAutomated    bool   `json:"is_automated"`
}

// runRelabel sets is_automated on stored emails with today's rules (Gmail's tabs as well as the headers;
// #224 item S). Without --write it only counts what would change.
func runRelabel(ctx context.Context, args []string) error {
	flags := flag.NewFlagSet("relabel", flag.ContinueOnError)
	isWrite := flags.Bool("write", false, "store the result (the default only counts)")
	if err := flags.Parse(args); err != nil {
		return err
	}
	connections, err := loadConnections(ctx)
	if err != nil {
		return fmt.Errorf("load connections: %w", err)
	}
	totals := map[string]int{}
	for _, connection := range connections {
		if err := relabelMailbox(ctx, connection, *isWrite, totals); err != nil {
			log.Printf("mailbox of user %s not relabelled: %v", connection.UserID, err)
		}
	}
	printTotals("relabel", totals, *isWrite)
	return nil
}

func relabelMailbox(ctx context.Context, connection connectionRow, isWrite bool, totals map[string]int) error {
	body, err := supabaseGet(ctx, "messages", "select=id,gmail_message_id,is_automated&"+ownerFilter(connection.UserID))
	if err != nil {
		return err
	}
	var rows []relabelRow
	if err := json.Unmarshal(body, &rows); err != nil {
		return fmt.Errorf("decode messages: %w", err)
	}
	srv, err := connectionService(ctx, connection)
	if err != nil {
		return fmt.Errorf("gmail: %w", err)
	}
	for _, row := range rows {
		totals[relabelOne(ctx, srv, row, isWrite)]++
	}
	return nil
}

func relabelOne(ctx context.Context, srv *gmail.Service, row relabelRow, isWrite bool) string {
	msg, err := srv.Users.Messages.Get("me", row.GmailMessageID).Format("metadata").
		MetadataHeaders(automatedHeaders...).Context(ctx).Do()
	time.Sleep(reprocessPause)
	switch {
	case isGone(err):
		return "skipped: " + skipGone
	case err != nil || msg.Payload == nil:
		return "skipped: " + skipFetchFailed
	}
	isNow := isAutomated(msg.Payload.Headers, msg.LabelIds)
	if isNow == row.IsAutomated {
		return "unchanged"
	}
	change := fmt.Sprintf("automated %t -> %t", row.IsAutomated, isNow)
	if !isWrite {
		return "would change: " + change
	}
	patch := map[string]bool{"is_automated": isNow}
	if err := supabasePatch(ctx, "messages", "id=eq."+url.QueryEscape(row.ID), patch); err != nil {
		log.Printf("email %s not stored: %v", row.ID, err)
		return "failed to store"
	}
	return "changed: " + change
}
