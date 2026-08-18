variable "project_id" {
  description = "GCP project ID hosting all CivicNexus resources."
  type        = string
}

variable "region" {
  description = "Single region for all resources (ARCHITECTURE.md §6.6 pins us-central1)."
  type        = string
  default     = "us-central1"
}

variable "billing_account_id" {
  description = "Billing account ID (XXXXXX-XXXXXX-XXXXXX) the budget alerts attach to."
  type        = string
}

variable "budget_amount_usd" {
  description = "Total budget in USD; alert thresholds are expressed against this."
  type        = number
  default     = 150
}

variable "alert_spend_usd" {
  description = "Absolute USD spend levels that trigger budget alerts (CLAUDE.md: 50/100/140)."
  type        = list(number)
  default     = [50, 100, 140]
}
