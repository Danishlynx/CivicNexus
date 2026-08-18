# Every API the platform needs (CLAUDE.md bootstrap list + supporting services).
locals {
  services = [
    "aiplatform.googleapis.com",       # Vertex AI: models, Agent Engine, RAG
    "run.googleapis.com",              # Cloud Run services
    "pubsub.googleapis.com",           # event bus
    "firestore.googleapis.com",        # case store
    "cloudtasks.googleapis.com",       # timers
    "cloudscheduler.googleapis.com",   # scheduled wakeups
    "bigquery.googleapis.com",         # audit + eval tables
    "cloudbuild.googleapis.com",       # CI + deploy from source
    "secretmanager.googleapis.com",    # secrets
    "cloudtrace.googleapis.com",       # tracing
    "modelarmor.googleapis.com",       # content screening
    "logging.googleapis.com",          # structured logs
    "monitoring.googleapis.com",       # alerting on log-based metrics
    "storage.googleapis.com",          # GCS buckets
    "artifactregistry.googleapis.com", # built images
    "iam.googleapis.com",              # per-agent service accounts
    "cloudresourcemanager.googleapis.com",
    "serviceusage.googleapis.com",
    "billingbudgets.googleapis.com", # budget alerts
    "cloudbilling.googleapis.com",   # billing account reads for budget setup
  ]
}

resource "google_project_service" "enabled" {
  for_each = toset(local.services)

  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}
