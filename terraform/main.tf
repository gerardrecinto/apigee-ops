resource "google_apigee_organization" "this" {
  project_id                           = var.project_id
  analytics_region                     = var.analytics_region
  authorized_network                   = var.authorized_network
  runtime_type                         = "CLOUD"
  billing_type                         = "PAYG"
  runtime_database_encryption_key_name = var.database_encryption_key_name
}

resource "google_apigee_instance" "this" {
  name                     = "apigee-${var.runtime_location}"
  location                 = var.runtime_location
  org_id                   = google_apigee_organization.this.id
  disk_encryption_key_name = var.disk_encryption_key_name
}

resource "google_apigee_environment" "this" {
  for_each = var.environments

  org_id       = google_apigee_organization.this.id
  name         = each.key
  display_name = each.key
  description  = "${each.key} environment"
}

resource "google_apigee_instance_attachment" "this" {
  for_each = var.environments

  instance_id = google_apigee_instance.this.id
  environment = google_apigee_environment.this[each.key].name
}

resource "google_apigee_envgroup" "this" {
  for_each = var.environments

  org_id    = google_apigee_organization.this.id
  name      = "${each.key}-group"
  hostnames = each.value.hostnames
}

resource "google_apigee_envgroup_attachment" "this" {
  for_each = var.environments

  envgroup_id = google_apigee_envgroup.this[each.key].id
  environment = google_apigee_environment.this[each.key].name
}

# KVM read by the KVM-Config policy in orders-api.
resource "google_apigee_environment_keyvaluemaps" "orders_config" {
  for_each = var.environments

  env_id = google_apigee_environment.this[each.key].id
  name   = "orders-config"
}

resource "google_apigee_target_server" "orders_backend" {
  for_each = var.environments

  name        = "orders-backend"
  env_id      = google_apigee_environment.this[each.key].id
  host        = var.orders_backend_host
  port        = 443
  protocol    = "HTTP"
  description = "Orders backend for ${each.key}"

  s_sl_info {
    enabled = true
  }
}

resource "google_apigee_environment_keyvaluemaps_entries" "cache_ttl" {
  for_each = var.environments

  env_keyvaluemap_id = google_apigee_environment_keyvaluemaps.orders_config[each.key].id
  name               = "cache.ttl.seconds"
  value              = tostring(each.value.cache_ttl_seconds)
}
