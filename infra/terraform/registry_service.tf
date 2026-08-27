# Registry on Cloud Run (§3.1, §6.2 selfhosted). Human-authorized 2026-08-20
# (Cloud Run pair). The image is built by Cloud Build from source; Terraform
# owns the service, its identity, and its access policy.

resource "google_artifact_registry_repository" "images" {
  repository_id = "civicnexus"
  location      = var.region
  format        = "DOCKER"

  depends_on = [google_project_service.enabled]
}

variable "registry_image" {
  description = "Full image URI for the registry service (built before apply)."
  type        = string
  # A8 (ratified 2026-08-27): non-empty default = the live deployed tag, so an
  # apply with a forgotten -var can never plan the LIVE registry service as
  # destroyed (the B-010 "3 to destroy" trap). Override only intentionally.
  default = "us-central1-docker.pkg.dev/civicnexus-hack26/civicnexus/registry:v0.1.0"
}

# Service identity: the registry runs as its own SA with exactly Firestore
# access (roles/datastore.user) — IAM grants in this file are applied only
# after the consolidated human ask (Working Agreement).
resource "google_service_account" "registry" {
  account_id   = "sa-registry"
  display_name = "Registry service (Cloud Run)"
}

resource "google_project_iam_member" "registry_datastore" {
  project = var.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.registry.email}"
}

resource "google_cloud_run_v2_service" "registry" {
  count    = var.registry_image == "" ? 0 : 1
  name     = "civicnexus-registry"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL" # auth enforced by IAM; no unauthenticated access

  # Hackathon service; replaceability matters more than delete-protection.
  deletion_protection = false

  template {
    service_account = google_service_account.registry.email
    scaling {
      max_instance_count = 2
    }
    containers {
      image = var.registry_image
      env {
        name  = "PROJECT_ID"
        value = var.project_id
      }
    }
  }

  depends_on = [google_project_service.enabled]
}

# B-007 experiment (human-approved 2026-08-21): identical service in a second
# region to test whether Google's edge routes it. Removed if it fails; becomes
# the primary if it works.
variable "registry_east_enabled" {
  type    = bool
  default = false
}

resource "google_cloud_run_v2_service" "registry_east" {
  count               = var.registry_east_enabled && var.registry_image != "" ? 1 : 0
  name                = "civicnexus-registry"
  location            = "us-east1"
  ingress             = "INGRESS_TRAFFIC_ALL"
  deletion_protection = false

  template {
    service_account = google_service_account.registry.email
    scaling {
      max_instance_count = 2
    }
    containers {
      image = var.registry_image
      env {
        name  = "PROJECT_ID"
        value = var.project_id
      }
    }
  }

  depends_on = [google_project_service.enabled]
}

resource "google_cloud_run_v2_service_iam_member" "registry_east_invokers" {
  for_each = var.registry_east_enabled && var.registry_image != "" ? {
    caseflow = "serviceAccount:sa-caseflow@${var.project_id}.iam.gserviceaccount.com"
    human    = "user:danishlynx@gmail.com"
  } : {}
  name     = google_cloud_run_v2_service.registry_east[0].name
  location = "us-east1"
  role     = "roles/run.invoker"
  member   = each.value
}

# Deny-by-default invokers: ONLY these principals may call the registry.
# (No allUsers binding anywhere — unauthenticated requests never reach the app.)
resource "google_cloud_run_v2_service_iam_member" "registry_invokers" {
  for_each = var.registry_image == "" ? {} : {
    caseflow = "serviceAccount:sa-caseflow@${var.project_id}.iam.gserviceaccount.com"
    human    = "user:danishlynx@gmail.com"
  }
  name     = google_cloud_run_v2_service.registry[0].name
  location = var.region
  role     = "roles/run.invoker"
  member   = each.value
}
