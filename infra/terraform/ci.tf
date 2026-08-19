# CI trigger (§9.4). The GitHub connection itself is a one-time human OAuth
# grant performed in the console 2026-08-19 (inherently manual — recorded in
# BLOCKERS B-002 resolution style per prime directive 6); the trigger and the
# build identity's permissions live here.

resource "google_cloudbuild_trigger" "ci_main" {
  name        = "civicnexus-ci"
  description = "Lint, types, unit+integration tests, and 12-case eval smoke on every push to main"
  location    = var.region

  github {
    owner = "Danishlynx"
    name  = "CivicNexus"
    push {
      branch = "^main$"
    }
  }

  filename = "cloudbuild.yaml"

  depends_on = [google_project_service.enabled]
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
