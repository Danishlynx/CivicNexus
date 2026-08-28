# Console on Cloud Run (ADR-007, asks A1-A5 ratified 2026-08-27). ONE image,
# TWO services with different exposures:
#
#   civicnexus-console       PUBLIC (allUsers invoker - the project's first and
#                            only public binding). Runs as sa-console-reader,
#                            whose ENTIRE permission set is roles/datastore.viewer:
#                            no model platform, no storage, no pubsub - a code bug
#                            cannot widen the blast radius (D13). CONSOLE_MODE
#                            defaults to reader in the app; set explicitly anyway.
#
#   civicnexus-console-clerk PRIVATE (named human only). Runs as sa-console-clerk
#                            with datastore.user + pubsub.publisher - the
#                            publisher grant is load-bearing: CaseStore._emit
#                            blocks on publish, so without it every clerk action
#                            hangs 10s and hard-fails (A3).
#
# The image variable has a NON-EMPTY default (A8) so an apply with a forgotten
# -var can never plan a live service for destruction (the B-010 trap class).

variable "console_image" {
  description = "Full image URI for the console service (built by Cloud Build before apply)."
  type        = string
  default     = "us-central1-docker.pkg.dev/civicnexus-hack26/civicnexus/console:v0.1.4"
}

resource "google_service_account" "console_reader" {
  account_id   = "sa-console-reader"
  display_name = "Console public reader (Cloud Run) - datastore.viewer ONLY"
}

resource "google_service_account" "console_clerk" {
  account_id   = "sa-console-clerk"
  display_name = "Console clerk (Cloud Run, private)"
}

# A1: the public reader reads cases/, incidents/, registry_agents/ and is
# structurally incapable of writing. This must stay the reader SA's ONLY role;
# verify_phase6 asserts the role list is exactly this (D13).
resource "google_project_iam_member" "console_reader_datastore_viewer" {
  project = var.project_id
  role    = "roles/datastore.viewer"
  member  = "serviceAccount:${google_service_account.console_reader.email}"
}

# A2: the clerk writes case transitions, approvals rows, and incident
# resolutions through the single-writer stores.
resource "google_project_iam_member" "console_clerk_datastore_user" {
  project = var.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.console_clerk.email}"
}

# A3: CaseStore._emit -> EventPublisher.publish blocks on future.result(10s);
# without this grant every clerk action hangs then hard-fails.
resource "google_project_iam_member" "console_clerk_pubsub_publisher" {
  project = var.project_id
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${google_service_account.console_clerk.email}"
}

resource "google_cloud_run_v2_service" "console_reader" {
  name                = "civicnexus-console"
  location            = var.region
  ingress             = "INGRESS_TRAFFIC_ALL"
  deletion_protection = false

  template {
    service_account = google_service_account.console_reader.email
    scaling {
      # D13: bounds cost under anonymous load; idle cost ~$0 at min 0.
      min_instance_count = 0
      max_instance_count = 2
    }
    containers {
      image = var.console_image
      env {
        name  = "PROJECT_ID"
        value = var.project_id
      }
      env {
        name  = "CONSOLE_MODE"
        value = "reader"
      }
    }
  }

  # The role grant is sequenced before the service so first traffic does not
  # race fresh-IAM propagation (the timers.tf lesson, 2026-08-27 audit).
  depends_on = [
    google_project_service.enabled,
    google_project_iam_member.console_reader_datastore_viewer,
  ]
}

resource "google_cloud_run_v2_service" "console_clerk" {
  name                = "civicnexus-console-clerk"
  location            = var.region
  ingress             = "INGRESS_TRAFFIC_ALL"
  deletion_protection = false

  template {
    service_account = google_service_account.console_clerk.email
    scaling {
      min_instance_count = 0
      max_instance_count = 2
    }
    containers {
      image = var.console_image
      env {
        name  = "PROJECT_ID"
        value = var.project_id
      }
      env {
        name  = "CONSOLE_MODE"
        value = "clerk"
      }
      # Attribution ground truth (measured 2026-08-28: Cloud Run consumes the
      # Authorization credential, so the app can never decode the caller).
      # Sound ONLY while run.invoker on this service is exactly this human -
      # verify_phase6 asserts that binding, so widening it turns the gate red.
      env {
        name  = "CLERK_SOLE_INVOKER"
        value = "danishlynx@gmail.com"
      }
    }
  }

  depends_on = [
    google_project_service.enabled,
    google_project_iam_member.console_clerk_datastore_user,
    google_project_iam_member.console_clerk_pubsub_publisher,
  ]
}

# A4: the mandatory judge-accessible hosted URL (Devpost testing clause). The
# ONLY allUsers binding in the project, on the READER service only.
resource "google_cloud_run_v2_service_iam_member" "console_reader_public" {
  name     = google_cloud_run_v2_service.console_reader.name
  location = var.region
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# The clerk service stays deny-by-default: the named human is the only
# invoker (verify_phase6 authenticates as this identity via ADC).
resource "google_cloud_run_v2_service_iam_member" "console_clerk_invoker" {
  name     = google_cloud_run_v2_service.console_clerk.name
  location = var.region
  role     = "roles/run.invoker"
  member   = "user:danishlynx@gmail.com"
}
