output "organization_id" {
  value = google_apigee_organization.this.id
}

output "envgroup_hostnames" {
  value = { for k, g in google_apigee_envgroup.this : k => g.hostnames }
}

output "tls_secret_ids" {
  value = { for k, s in google_secret_manager_secret.tls : k => s.secret_id }
}
