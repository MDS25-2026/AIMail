package main

import (
	"fmt"
	"os"
	"strings"
)

// The Pub/Sub settings have no defaults: a deployment that forgot them must not quietly watch
// another project's topic.
const (
	envGCPProject         = "GCP_PROJECT_ID"
	envPubSubTopic        = "PUBSUB_TOPIC"
	envPubSubSubscription = "PUBSUB_SUBSCRIPTION"
)

type pubsubConfig struct {
	projectID      string
	topicID        string // the short id, e.g. gmail-notifications, not the projects/... path
	subscriptionID string
}

// pubsubTopic is the full topic path every Gmail watch notifies; set in main once the config loads.
var pubsubTopic string

func loadPubSubConfig() (pubsubConfig, error) {
	cfg := pubsubConfig{
		projectID:      os.Getenv(envGCPProject),
		topicID:        os.Getenv(envPubSubTopic),
		subscriptionID: os.Getenv(envPubSubSubscription),
	}
	var missing []string
	for _, setting := range [][2]string{
		{envGCPProject, cfg.projectID}, {envPubSubTopic, cfg.topicID}, {envPubSubSubscription, cfg.subscriptionID},
	} {
		if strings.TrimSpace(setting[1]) == "" {
			missing = append(missing, setting[0])
		}
	}
	if len(missing) > 0 {
		return cfg, fmt.Errorf("%s not set; see .env.example", strings.Join(missing, ", "))
	}
	return cfg, nil
}

func (c pubsubConfig) topicPath() string {
	return fmt.Sprintf("projects/%s/topics/%s", c.projectID, c.topicID)
}
