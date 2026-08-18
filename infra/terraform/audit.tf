# Audit trail (§4: every transition = one Pub/Sub event + one BigQuery audit
# row; §8: structured logs post-redaction route to BigQuery via a log sink).
# Services emit JSON logs with `audit: true`; the sink lands them in the
# `audit` dataset append-only.

resource "google_bigquery_dataset" "audit" {
  dataset_id  = "audit"
  description = "Append-only audit trail: case transitions, agent actions, reasoning."
  location    = var.region

  depends_on = [google_project_service.enabled]
}

resource "google_logging_project_sink" "audit_to_bq" {
  name        = "civicnexus-audit-to-bq"
  destination = "bigquery.googleapis.com/projects/${var.project_id}/datasets/${google_bigquery_dataset.audit.dataset_id}"
  filter      = "jsonPayload.audit=true"

  bigquery_options {
    use_partitioned_tables = true
  }

  unique_writer_identity = true
}

resource "google_bigquery_dataset_iam_member" "audit_sink_writer" {
  dataset_id = google_bigquery_dataset.audit.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = google_logging_project_sink.audit_to_bq.writer_identity
}
