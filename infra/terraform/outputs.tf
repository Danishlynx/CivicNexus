output "enabled_apis" {
  description = "APIs enabled on the project."
  value       = [for s in google_project_service.enabled : s.service]
}

output "budget_name" {
  description = "Resource name of the hackathon budget (proof for make bootstrap)."
  value       = google_billing_budget.civicnexus.name
}

output "budget_threshold_percents" {
  description = "Applied alert thresholds as fractions of the budget (proof the alerts exist)."
  value       = [for r in google_billing_budget.civicnexus.threshold_rules : r.threshold_percent]
}

output "agent_staging_bucket" {
  description = "GCS bucket used to stage Agent Engine deployments."
  value       = google_storage_bucket.agent_staging.name
}
