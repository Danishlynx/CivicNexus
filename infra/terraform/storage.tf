# Staging bucket for Agent Engine deployments (required by Vertex AI deploy flow).
resource "google_storage_bucket" "agent_staging" {
  name                        = "${var.project_id}-agent-staging"
  location                    = var.region
  uniform_bucket_level_access = true
  force_destroy               = true

  depends_on = [google_project_service.enabled]
}
