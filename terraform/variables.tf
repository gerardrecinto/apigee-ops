variable "project_id" {
  description = "GCP project that owns the Apigee organization."
  type        = string
}

variable "analytics_region" {
  description = "Region where Apigee analytics data is stored."
  type        = string
  default     = "us-west1"
}

variable "authorized_network" {
  description = "VPC network id (projects/PROJECT/global/networks/NAME) peered to Apigee."
  type        = string
}

variable "runtime_location" {
  description = "Region of the Apigee runtime instance."
  type        = string
  default     = "us-west1"
}

variable "database_encryption_key_name" {
  description = "Cloud KMS key that encrypts the Apigee runtime database."
  type        = string
}

variable "disk_encryption_key_name" {
  description = "Cloud KMS key that encrypts the runtime instance disk."
  type        = string
}

variable "environments" {
  description = "Environments to create. hostnames feed the environment group, cache_ttl_seconds seeds the orders-config KVM."
  type = map(object({
    hostnames         = list(string)
    cache_ttl_seconds = number
  }))
  default = {
    test = {
      hostnames         = ["api-test.example.com"]
      cache_ttl_seconds = 10
    }
    prod = {
      hostnames         = ["api.example.com"]
      cache_ttl_seconds = 60
    }
  }
}

variable "orders_backend_host" {
  description = "Host name of the orders backend behind the target server."
  type        = string
  default     = "orders-backend.example.internal"
}
