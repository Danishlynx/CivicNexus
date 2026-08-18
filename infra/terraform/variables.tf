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

variable "budget_currency" {
  description = "Currency of the budget — MUST match the billing account's currency or the API rejects the budget with a bare INVALID_ARGUMENT."
  type        = string
  default     = "USD"
}

variable "budget_amount" {
  description = "Total budget ceiling in budget_currency units (spec intent: ~USD 150)."
  type        = number
  default     = 150
}

variable "alert_spend" {
  description = "Absolute spend levels (in budget_currency) that trigger alerts (spec intent: ~USD 50/100/140)."
  type        = list(number)
  default     = [50, 100, 140]
}
