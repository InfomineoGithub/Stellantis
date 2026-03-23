terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  credentials = file(var.credentials_file)
  project     = var.project_id
}

# Enable API Keys API
resource "google_project_service" "apikeys" {
  project            = var.project_id
  service            = "apikeys.googleapis.com"
  disable_on_destroy = false
}

# Enable Gemini API
resource "google_project_service" "gemini" {
  project            = var.project_id
  service            = "generativelanguage.googleapis.com"
  disable_on_destroy = false
}

resource "google_apikeys_key" "ragflow_api_key" {
  name         = var.key_name
  display_name = var.key_display_name
  project      = var.project_id

  restrictions {
    api_targets {
      service = "generativelanguage.googleapis.com"
    }
  }

  depends_on = [
    google_project_service.apikeys,
    google_project_service.gemini
  ]
}

output "api_key_string" {
  value     = google_apikeys_key.ragflow_api_key.key_string
  sensitive = true
}
