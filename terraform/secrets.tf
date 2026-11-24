# One secret per environment holds the TLS certificate and key as JSON.
# scripts in src/apigee_ops/certs.py add new versions; Terraform owns only the container.
resource "google_secret_manager_secret" "tls" {
  for_each = var.environments

  project   = var.project_id
  secret_id = "apigee-tls-${each.key}"

  replication {
    auto {}
  }

  labels = {
    purpose = "apigee-tls"
    env     = each.key
  }
}
