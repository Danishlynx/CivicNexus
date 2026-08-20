# Per-agent identities (§6.1, ADR-003 decision 2: SAs as baseline).
# Human-authorized 2026-08-20: 4 SAs, each granted roles/aiplatform.user —
# reason: their agents must call models and query the RAG corpus.
locals {
  agent_sas = {
    "sa-caseflow" = "Caseflow fleet agent (coordinator, intake, zoning)"
    "sa-safety"   = "Safety reviewer agent"
    "sa-letters"  = "Letters drafting agent (draft-only, never sends)"
    "sa-treepres" = "Tree preservation agent (hot-add demo)"
  }
}

resource "google_service_account" "agents" {
  for_each     = local.agent_sas
  account_id   = each.key
  display_name = each.value
}

resource "google_project_iam_member" "agents_aiplatform_user" {
  for_each = local.agent_sas
  project  = var.project_id
  role     = "roles/aiplatform.user"
  member   = "serviceAccount:${google_service_account.agents[each.key].email}"
}

# Human-authorized 2026-08-20 (follow-up ask): the deployer must hold actAs on
# each agent SA to bind it to an Agent Engine runtime — scoped to these four
# SAs only, never project-wide.
resource "google_service_account_iam_member" "deployer_act_as" {
  for_each           = local.agent_sas
  service_account_id = google_service_account.agents[each.key].name
  role               = "roles/iam.serviceAccountUser"
  member             = "user:danishlynx@gmail.com"
}

# Human-authorized 2026-08-20 (item c): Data Access audit logs for Vertex —
# reason: the deliberate-deny test must produce an auditable 403 entry.
resource "google_project_iam_audit_config" "aiplatform_data_access" {
  project = var.project_id
  service = "aiplatform.googleapis.com"

  audit_log_config {
    log_type = "DATA_READ"
  }
  audit_log_config {
    log_type = "DATA_WRITE"
  }
}
