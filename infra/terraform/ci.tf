# CI trigger (§9.4). The GitHub connection itself is a one-time human OAuth
# grant performed in the console 2026-08-19 (inherently manual — recorded in
# BLOCKERS B-002 resolution style per prime directive 6); the trigger and the
# build identity's permissions live here.

# 2nd-gen path: Google no longer accepts new triggers on 1st-gen GitHub App
# connections (bare 400s; confirmed against live docs 2026-08-19). The v2
# connection + repo link were created via console OAuth + gcloud
# (`gcloud builds repositories create CivicNexus --connection=github-danishlynx`);
# the trigger lives here.
resource "google_cloudbuild_trigger" "ci_main" {
  name        = "civicnexus-ci"
  description = "Lint, types, unit+integration tests, and 12-case eval smoke on every push to main"
  location    = var.region

  repository_event_config {
    repository = "projects/${var.project_id}/locations/${var.region}/connections/github-danishlynx/repositories/CivicNexus"
    push {
      branch = "^main$"
    }
  }

  filename = "cloudbuild.yaml"

  # New projects have no legacy Cloud Build SA; triggers must name an identity.
  # The compute default SA already carries roles/aiplatform.user for the
  # eval-smoke step; cloudbuild.yaml sets CLOUD_LOGGING_ONLY as this requires.
  service_account = "projects/${var.project_id}/serviceAccounts/${data.google_project.this.number}-compute@developer.gserviceaccount.com"

  depends_on = [google_project_service.enabled]
}

# The named build SA (compute default) needs Cloud Build's own working set —
# log writing and builder permissions — or builds die with INTERNAL_ERROR
# before any step runs (observed on first triggered build, 2026-08-19).
resource "google_project_iam_member" "compute_default_builder" {
  project = var.project_id
  role    = "roles/cloudbuild.builds.builder"
  member  = "serviceAccount:${data.google_project.this.number}-compute@developer.gserviceaccount.com"
}

resource "google_project_iam_member" "compute_default_log_writer" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${data.google_project.this.number}-compute@developer.gserviceaccount.com"
}

# The eval-smoke step queries the deployed Agent Engine instance as the build
# identity. Cover both identities Cloud Build may run as (legacy build SA and
# the compute default SA, depending on project settings).
resource "google_project_iam_member" "cloudbuild_vertex_user" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${data.google_project.this.number}@cloudbuild.gserviceaccount.com"
}

resource "google_project_iam_member" "compute_default_vertex_user" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${data.google_project.this.number}-compute@developer.gserviceaccount.com"
}
