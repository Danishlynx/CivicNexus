# Phase 5 infrastructure (ADR-006 D5, D6, D13, D16, D17).
#
# Model Armor returns verdicts; it does not block. Enforcement is ours: the
# pipeline reads filterMatchState and quarantines (D3). enforcement_type below
# is a statement of intent recorded in the template, not a server-side gate.
#
# Recurring cost ~= $0: Model Armor is free to 2M tokens/month (A-8), the
# quarantine bucket holds a handful of drill documents, and the three
# subscriptions are drill-lifecycle only.

resource "google_model_armor_template" "civicnexus" {
  location    = var.region
  template_id = "civicnexus-armor"

  filter_config {
    # The two blocking filters (D4): a MATCH here is what quarantines content
    # and what the "injection block 15/15" gate counts.
    # confidence_level is the MINIMUM confidence at which the filter reports a
    # match, so HIGH is the least sensitive setting, not the strongest. It was
    # measured at HIGH and found blind to this product's actual threat: a
    # sensitivity ladder (B-014) showed instruction override, role negation and
    # persona replacement all pass unflagged, and only a system-prompt
    # disclosure demand trips it. A permit system is attacked with "approve my
    # permit", not "reveal your system prompt".
    #
    # MEDIUM_AND_ABOVE is the setting under test. The canary's negative arm is
    # the acceptance test — 12 controls / 0 false positives at HIGH is the
    # baseline, so any cost of the added sensitivity is measured, not assumed.
    pi_and_jailbreak_filter_settings {
      filter_enforcement = "ENABLED"
      confidence_level   = "MEDIUM_AND_ABOVE"
    }

    # No confidence knob exists on this filter — recorded delta, confirmed
    # against the provider schema at v7.44.0.
    malicious_uri_filter_settings {
      filter_enforcement = "ENABLED"
    }

    # Advisory at screening points 1-3 and blocking at point 4 (D4).
    # Applications legitimately carry applicant PII, so an SDP match on benign
    # contact data must never quarantine a case; the verdict is recorded and
    # feeds the §6.6 redactor story. Detection only — redaction needs DLP
    # templates, deferred (recorded delta from §6.3's "sensitive data → redact").
    sdp_settings {
      basic_config {
        filter_enforcement = "ENABLED"
      }
    }
  }

  template_metadata {
    log_sanitize_operations = true
    log_template_operations = true
    enforcement_type        = "INSPECT_AND_BLOCK"
  }

  depends_on = [google_project_service.enabled]
}

# Quarantine destination for blocked content (D6). Never a silent drop: the
# original bytes land here, an Incident is written, and the case transitions to
# QUARANTINED with human-only exits.
resource "google_storage_bucket" "docs_quarantine" {
  name                        = "${var.project_id}-docs-quarantine"
  location                    = var.region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"

  # Hackathon fixture data; clean teardown matters more than retention.
  force_destroy = true

  depends_on = [google_project_service.enabled]
}

# --- Drill subscriptions (D13, D16) -----------------------------------------
# These two carry a recorded exemption from the §5 "every subscription has a
# DLQ" rule: they are drill-lifecycle, driver-pulled, and have no service
# consumer, so a DLQ on them would have nothing to protect.

# Dead-letters after 5 failed deliveries so dlq_replay has a real mechanism to
# exercise rather than a simulated one.
resource "google_pubsub_subscription" "timer_fired_drill" {
  name  = "timer-fired-drill"
  topic = google_pubsub_topic.events["timer.fired"].id

  ack_deadline_seconds = 10

  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.timer_fired_dlq.id
    max_delivery_attempts = 5
  }

  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "60s"
  }
}

# Without this grant Pub/Sub cannot forward to the DLQ at all — proven the hard
# way on timer-fired-demo, where the Phase 4 apply died before creating the
# equivalent binding and dead-lettering silently did not work (B-010).
resource "google_pubsub_subscription_iam_member" "drill_dlq_subscriber" {
  subscription = google_pubsub_subscription.timer_fired_drill.name
  role         = "roles/pubsub.subscriber"
  member       = "serviceAccount:service-${data.google_project.this.number}@gcp-sa-pubsub.iam.gserviceaccount.com"
}

# Pull subscription the replay drill reads dead letters from.
resource "google_pubsub_subscription" "timer_fired_dlq_replay" {
  name  = "timer-fired-dlq-replay"
  topic = google_pubsub_topic.timer_fired_dlq.id

  ack_deadline_seconds = 60
}

# demo_injection asserts incident.raised was published with a byte-equal
# traceparent, which needs a subscription in place before the event fires.
resource "google_pubsub_subscription" "incident_raised_demo" {
  name  = "incident-raised-demo"
  topic = google_pubsub_topic.events["incident.raised"].id

  ack_deadline_seconds = 60
}
