# Phase 4 durability: case wakeup timers (§3.1). Human-authorized 2026-08-26
# (Phase 4 consolidated ask). Cost projection: ~$0 (queue unbilled; first 1M
# task operations/month free; demo volume is a handful).

resource "google_cloud_tasks_queue" "case_timers" {
  name     = "case-timers"
  location = var.region

  retry_config {
    max_attempts = 5
    # Default sub-second backoffs would burn all 5 attempts in ~3s — too
    # fast to survive fresh-IAM propagation on the publish binding.
    min_backoff   = "30s"
    max_backoff   = "300s"
    max_doublings = 3
  }

  depends_on = [google_project_service.enabled]
}

# Timer delivery identity: Cloud Tasks authenticates to Pub/Sub's publish
# endpoint as this SA. Publish rights scoped to the timer.fired topic ONLY —
# no agent SA gains publish rights (§6.1 separation).
resource "google_service_account" "timers" {
  account_id   = "sa-timers"
  display_name = "Case timer delivery (Cloud Tasks -> Pub/Sub)"
}

resource "google_pubsub_topic_iam_member" "timers_publisher" {
  topic  = google_pubsub_topic.events["timer.fired"].name
  role   = "roles/pubsub.publisher"
  member = "serviceAccount:${google_service_account.timers.email}"
}

# The task-enqueueing driver must actAs the task's OAuth identity.
resource "google_service_account_iam_member" "timers_act_as" {
  service_account_id = google_service_account.timers.name
  role               = "roles/iam.serviceAccountUser"
  member             = "user:danishlynx@gmail.com"
}

# Demo consumer subscription (§5 rule: every subscription has a DLQ).
resource "google_pubsub_topic" "timer_fired_dlq" {
  name = "timer.fired.dlq"

  depends_on = [google_project_service.enabled]
}

resource "google_pubsub_subscription" "timer_fired_demo" {
  name  = "timer-fired-demo"
  topic = google_pubsub_topic.events["timer.fired"].id

  ack_deadline_seconds = 60

  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.timer_fired_dlq.id
    max_delivery_attempts = 5
  }

  retry_policy {
    minimum_backoff = "5s"
    maximum_backoff = "60s"
  }
}

# DLQ plumbing: the Pub/Sub service agent needs to move messages (reuses the
# project data source declared in budget.tf).
resource "google_pubsub_topic_iam_member" "dlq_publisher" {
  topic  = google_pubsub_topic.timer_fired_dlq.name
  role   = "roles/pubsub.publisher"
  member = "serviceAccount:service-${data.google_project.this.number}@gcp-sa-pubsub.iam.gserviceaccount.com"
}

resource "google_pubsub_subscription_iam_member" "dlq_subscriber" {
  subscription = google_pubsub_subscription.timer_fired_demo.name
  role         = "roles/pubsub.subscriber"
  member       = "serviceAccount:service-${data.google_project.this.number}@gcp-sa-pubsub.iam.gserviceaccount.com"
}
