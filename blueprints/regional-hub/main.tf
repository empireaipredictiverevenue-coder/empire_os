# Empire OS v3 - Regional Hub Deployment Blueprint
# Terraform + Incus + DB Schema for franchise deployment

# ─────────────────────────────────────────────────────────────────────
# Terraform: Regional Hub Infrastructure
# ─────────────────────────────────────────────────────────────────────

terraform {
  required_version = ">= 1.5"
  required_providers {
    incus = {
      source  = "bionic-gopher/incus"
      version = "~> 1.0"
    }
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "~> 4.0"
    }
  }
}

provider "incus" {
  endpoint = "unix:///var/lib/incus/unix.socket"
}

provider "cloudflare" {
  api_token = var.cloudflare_api_token
}

# ─────────────────────────────────────────────────────────────────────
# Variables
# ─────────────────────────────────────────────────────────────────────

variable "region" {
  description = "Regional hub identifier (usa-east, usa-central, usa-west)"
  type        = string
  validation {
    condition     = contains(["usa-east", "usa-central", "usa-west"], var.region)
    error_message = "Region must be usa-east, usa-central, or usa-west."
  }
}

variable "metro_list" {
  description = "List of metros this hub owns"
  type        = list(string)
  default     = []
}

variable "cloudflare_api_token" {
  description = "Cloudflare API token for DNS management"
  type        = string
  sensitive   = true
}

variable "empire_core_api_key" {
  description = "API key for empire-core communication"
  type        = string
  sensitive   = true
}

variable "postgres_password" {
  description = "PostgreSQL password for regional DB"
  type        = string
  sensitive   = true
}

variable "redis_password" {
  description = "Redis password for regional cache"
  type        = string
  sensitive   = true
}

# ─────────────────────────────────────────────────────────────────────
# Incus Profile for Regional Hub
# ─────────────────────────────────────────────────────────────────────

resource "incus_profile" "regional_hub" {
  name        = "regional-hub-${var.region}"
  description = "Profile for ${var.region} regional hub container"
  config = {
    "limits.cpu"           = "4"
    "limits.memory"        = "8GB"
    "limits.disk"          = "100GB"
    "security.nesting"     = "true"
    "security.privileged"  = "false"
    "user.network_mode"    = "managed"
    "boot.autostart"       = "true"
  }
  devices = {
    "eth0" = {
      type  = "nic"
      name  = "eth0"
      nictype = "bridged"
      parent = "incusbr0"
      ipv4.address = "auto"
      ipv6.address = "auto"
    }
    "root" = {
      type = "disk"
      path = "/"
      pool = "default"
      size = "100GB"
    }
  }
}

# ─────────────────────────────────────────────────────────────────────
# Regional Hub Container
# ─────────────────────────────────────────────────────────────────────

resource "incus_instance" "regional_hub" {
  name        = "regional-hub-${var.region}"
  image       = "images:ubuntu/22.04/cloud"
  type        = "container"
  profiles    = ["default", incus_profile.regional_hub.name]
  
  # Cloud-init for bootstrap
  cloud_init = templatefile("${path.module}/cloud-init/regional-hub.yaml.tpl", {
    region            = var.region
    metros            = var.metro_list
    empire_core_key   = var.empire_core_api_key
    postgres_password = var.postgres_password
    redis_password    = var.redis_password
  })
  
  # Wait for cloud-init to complete
  provisioner "remote-exec" {
    inline = [
      "sleep 30",
      "systemctl is-active --quiet empire-hub || exit 1",
      "curl -sf http://localhost:8081/health || exit 1",
    ]
  }
}

# ─────────────────────────────────────────────────────────────────────
# Cloudflare DNS Records for Regional Hub
# ─────────────────────────────────────────────────────────────────────

resource "cloudflare_record" "regional_hub_api" {
  zone_id = var.cloudflare_zone_id
  name    = "api-${var.region}"
  value   = incus_instance.regional_hub.network.0.ipv4.address
  type    = "A"
  proxied = true
  ttl     = 300
  comment = "Empire OS ${var.region} regional hub API"
}

resource "cloudflare_record" "regional_hub_intake" {
  zone_id = var.cloudflare_zone_id
  name    = "intake-${var.region}"
  value   = incus_instance.regional_hub.network.0.ipv4.address
  type    = "A"
  proxied = true
  ttl     = 300
  comment = "Empire OS ${var.region} regional hub intake endpoint"
}

resource "cloudflare_record" "regional_hub_cortex" {
  zone_id = var.cloudflare_zone_id
  name    = "cortex-${var.region}"
  value   = incus_instance.regional_hub.network.0.ipv4.address
  type    = "A"
  proxied = true
  ttl     = 300
  comment = "Empire OS ${var.region} regional hub Cortex API"
}

# ─────────────────────────────────────────────────────────────────────
# Cloudflare Worker for Geo-Routing (per region)
# ─────────────────────────────────────────────────────────────────────

resource "cloudflare_worker_script" "geo_router" {
  name     = "empire-geo-router-${var.region}"
  content  = file("${path.module}/workers/geo-router.js")
  module   = true
  
  # KV bindings for rate limiting
  kv_namespace_bindings = [
    {
      name = "RATE_LIMIT_KV"
      namespace_id = cloudflare_workers_kv_namespace.rate_limit.id
    },
    {
      name = "ANALYTICS_KV"
      namespace_id = cloudflare_workers_kv_namespace.analytics.id
    }
  ]
}

resource "cloudflare_workers_kv_namespace" "rate_limit" {
  title = "empire-rate-limit-${var.region}"
}

resource "cloudflare_workers_kv_namespace" "analytics" {
  title = "empire-analytics-${var.region}"
}

resource "cloudflare_worker_route" "geo_router" {
  zone_id = var.cloudflare_zone_id
  pattern = "api-${var.region}.empire-ai.co.uk/*"
  script_name = cloudflare_worker_script.geo_router.name
}

# ─────────────────────────────────────────────────────────────────────
# Outputs
# ─────────────────────────────────────────────────────────────────────

output "hub_ip" {
  value = incus_instance.regional_hub.network.0.ipv4.address
  description = "Regional hub IP address"
}

output "api_endpoint" {
  value = "https://api-${var.region}.empire-ai.co.uk"
  description = "Public API endpoint for regional hub"
}

output "intake_endpoint" {
  value = "https://intake-${var.region}.empire-ai.co.uk"
  description = "Public intake endpoint for regional hub"
}

output "cortex_endpoint" {
  value = "https://cortex-${var.region}.empire-ai.co.uk"
  description = "Public Cortex API endpoint for regional hub"
}