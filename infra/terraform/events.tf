# Event bus topics — one per event type in ARCHITECTURE.md §5.
# Topic IDs equal the envelope `type` strings verbatim (periods are legal in
# Pub/Sub topic IDs), so no mapping layer can drift.
locals {
  event_topics = [
    "case.received",
    "case.triaged",
    "review.requested",
    "review.completed",
    "verification.failed",
    "applicant.message",
    "timer.fired",
    "action.pending_approval",
    "action.approved",
    "letter.sent",
    "incident.raised",
    "case.closed",
  ]
}

resource "google_pubsub_topic" "events" {
  for_each = toset(local.event_topics)

  name = each.value

  depends_on = [google_project_service.enabled]
}
