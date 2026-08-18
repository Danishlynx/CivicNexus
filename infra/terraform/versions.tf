terraform {
  required_version = ">= 1.9"

  # Local state for Phase 0 (no bucket exists before first apply). A GCS backend
  # is added once the project exists — recorded in ASSUMPTIONS.md.
  required_providers {
    google = {
      source = "hashicorp/google"
      # Floor 6.43: first version with google_model_armor_template (needed Phase 5);
      # latest at scaffold time was 7.44.
      version = ">= 6.43, < 8.0"
    }
  }
}
