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

# IAM redesign (human-approved 2026-08-20): agents hold ONLY the custom base
# role. roles/aiplatform.user turned out to include reasoningEngines
# query/create/update/DELETE project-wide — revoked. Rollout is staged via
# local.converted_sas (safety first, smoke-verified, then all).
locals {
  converted_sas = ["sa-safety", "sa-caseflow", "sa-letters", "sa-treepres"]
}

resource "google_project_iam_custom_role" "agent_base" {
  role_id     = "civicnexusAgentBase"
  title       = "CivicNexus agent base"
  description = "Exactly what a reviewer agent needs: model calls + read/query the RAG corpus."
  permissions = [
    "aiplatform.endpoints.predict",
    "aiplatform.ragCorpora.get",
    "aiplatform.ragCorpora.query",
    "aiplatform.ragEngineConfigs.get",
    # Runtime plumbing: the agent's ADK session service manages its own
    # sessions under the agent identity (verified: sessions.create denial
    # broke the min-role smoke). Project-scoped for now; invoke rights stay
    # per-resource — refinement noted in ADR-003.
    "aiplatform.sessions.create",
    "aiplatform.sessions.get",
    "aiplatform.sessions.list",
    "aiplatform.sessions.update",
    "aiplatform.sessionEvents.append",
    "aiplatform.sessionEvents.list",
  ]
}

resource "google_project_iam_custom_role" "engine_caller" {
  role_id     = "civicnexusEngineCaller"
  title       = "CivicNexus engine caller"
  description = "Query one specific agent engine (granted per-resource, never project-wide)."
  permissions = [
    "aiplatform.reasoningEngines.get",
    "aiplatform.reasoningEngines.query",
  ]
}

resource "google_project_iam_member" "agents_base_role" {
  for_each = toset(local.converted_sas)
  project  = var.project_id
  role     = google_project_iam_custom_role.agent_base.id
  member   = "serviceAccount:${google_service_account.agents[each.key].email}"
}

# Legacy broad role remains ONLY on not-yet-converted SAs during the staged
# rollout; this block empties as conversion completes.
resource "google_project_iam_member" "agents_aiplatform_user" {
  for_each = { for k, v in local.agent_sas : k => v if !contains(local.converted_sas, k) }
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

# Human-authorized 2026-08-20 (deny-matrix ask): the test harness impersonates
# exactly these two identities to PROVE the per-resource matrix (positive and
# negative cases). Scoped to the two SAs, never project-wide.
resource "google_service_account_iam_member" "harness_token_creator" {
  for_each           = toset(["sa-caseflow", "sa-safety"])
  service_account_id = google_service_account.agents[each.key].name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = "user:danishlynx@gmail.com"
}

# Human-authorized 2026-08-21 (B-007 interim ask): roles/datastore.viewer →
# sa-caseflow — reason: the coordinator reads APPROVED cards from
# registry_agents directly while Google's edge won't route the registry
# service (ADR-003 addendum). Read-only. Firestore has no row-level IAM, so
# the grant is datastore-wide (§6.1 acknowledged limitation). REMOVE when
# reverting to REGISTRY_MODE=http.
resource "google_project_iam_member" "caseflow_registry_read_interim" {
  project = var.project_id
  role    = "roles/datastore.viewer"
  member  = "serviceAccount:${google_service_account.agents["sa-caseflow"].email}"
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
