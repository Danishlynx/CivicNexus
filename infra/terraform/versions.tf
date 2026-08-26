terraform {
  required_version = ">= 1.9"

  # Remote state since 2026-08-26. Local state truncated to 0 bytes twice
  # (B-008, B-010) and a third NUL-truncation hit .git (B-012), so the local
  # file is a proven single point of failure. The bucket is versioned, so a
  # truncated write is recoverable by generation rather than by backup luck.
  #
  # Created out-of-band with gcloud (recorded in BLOCKERS per directive 6): a
  # state bucket managed by the state it holds is a bootstrap cycle, and the
  # only other buckets are Terraform-managed and unversioned.
  backend "gcs" {
    bucket = "civicnexus-hack26-tfstate"
    prefix = "infra"
  }
  required_providers {
    google = {
      source = "hashicorp/google"
      # Floor 6.43: first version with google_model_armor_template (needed Phase 5);
      # latest at scaffold time was 7.44.
      version = ">= 6.43, < 8.0"
    }
  }
}
