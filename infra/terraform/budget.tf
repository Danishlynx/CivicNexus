data "google_project" "this" {
  project_id = var.project_id

  depends_on = [google_project_service.enabled]
}

# Budget with alerts at absolute $50/$100/$140 spend (CLAUDE.md bootstrap contract).
# With no explicit notification channel, Google emails the billing account admins.
resource "google_billing_budget" "civicnexus" {
  billing_account = var.billing_account_id
  display_name    = "civicnexus-hackathon"

  budget_filter {
    projects = ["projects/${data.google_project.this.number}"]
    # Alert on gross spend: promo/trial credits must not mute the alerts by
    # netting spend to zero.
    credit_types_treatment = "EXCLUDE_ALL_CREDITS"
  }

  amount {
    specified_amount {
      currency_code = var.budget_currency
      units         = tostring(floor(var.budget_amount))
    }
  }

  dynamic "threshold_rules" {
    for_each = var.alert_spend
    content {
      threshold_percent = threshold_rules.value / var.budget_amount
      spend_basis       = "CURRENT_SPEND"
    }
  }
}
