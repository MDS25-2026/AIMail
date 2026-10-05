# Pub/Sub dead-letter policy for Gmail notifications

The listener gives up on a notification after `maxDeliveryAttempts` (5) failures, audits it as
`ingest_abandoned`, and moves its history baseline past it (`listener/main.go`). It can only count
attempts if the subscription has a **dead-letter policy**: without one, Pub/Sub never fills in
`DeliveryAttempt`, so a notification that always fails is redelivered forever. The listener logs a
warning once at the first failure when the policy is missing.

A dead-letter topic is the platform's own mechanism: the count survives listener restarts, it stays
correct with more than one listener running, and failed notifications are kept for inspection.

## One-time setup

Project `aimail-505405`, subscription `gmail-notifications-sub` (constants in `listener/main.go`).
Run once with `gcloud` signed in as a project owner:

```bash
PROJECT=aimail-505405
gcloud config set project "$PROJECT"

# Where notifications go after 5 failed deliveries, and a subscription to inspect them.
gcloud pubsub topics create gmail-notifications-dead-letter
gcloud pubsub subscriptions create gmail-notifications-dead-letter-sub \
  --topic=gmail-notifications-dead-letter

# Attach it, with backoff between retries instead of immediate redelivery.
gcloud pubsub subscriptions update gmail-notifications-sub \
  --dead-letter-topic=gmail-notifications-dead-letter \
  --max-delivery-attempts=5 \
  --min-retry-delay=10s --max-retry-delay=600s

# Pub/Sub's own service account must be able to move messages to the dead-letter topic.
NUMBER=$(gcloud projects describe "$PROJECT" --format='value(projectNumber)')
AGENT="serviceAccount:service-$NUMBER@gcp-sa-pubsub.iam.gserviceaccount.com"
gcloud pubsub topics add-iam-policy-binding gmail-notifications-dead-letter \
  --member="$AGENT" --role=roles/pubsub.publisher
gcloud pubsub subscriptions add-iam-policy-binding gmail-notifications-sub \
  --member="$AGENT" --role=roles/pubsub.subscriber
```

Keep `--max-delivery-attempts` equal to `maxDeliveryAttempts` in the listener, so the listener
records the give-up before Pub/Sub moves the message.

## Check it worked

```bash
gcloud pubsub subscriptions describe gmail-notifications-sub --format='yaml(deadLetterPolicy,retryPolicy)'
```

The same steps work in the console: Pub/Sub, Subscriptions, `gmail-notifications-sub`, Edit,
"Dead lettering".
