# Runtime identity grants.
#
# Phase 1: deployed agents run as the shared Reasoning Engine service agent,
# which needs Vertex access for RAG retrieval (observed 403 on
# aiplatform.ragCorpora.get at first live run). Phase 3 replaces this with
# per-agent service accounts and least-privilege scopes (§6.1) — this grant is
# deliberately the coarse interim, tracked for replacement.
resource "google_project_iam_member" "reasoning_engine_vertex_user" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:service-${data.google_project.this.number}@gcp-sa-aiplatform-re.iam.gserviceaccount.com"
}
