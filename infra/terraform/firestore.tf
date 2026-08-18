# Case store database (§3.2): Firestore native mode, single region.
resource "google_firestore_database" "cases" {
  name        = "(default)"
  location_id = var.region
  type        = "FIRESTORE_NATIVE"

  depends_on = [google_project_service.enabled]
}
