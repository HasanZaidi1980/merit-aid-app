# Cheapest-viable GCP footprint for a student project.
# terraform init && terraform apply -var project_id=YOUR_PROJECT -var bucket_name=YOUR_BUCKET
terraform {
  required_providers {
    google = { source = "hashicorp/google", version = "~> 5.0" }
  }
}
provider "google" {
  project = var.project_id
  region  = var.region
}

# --- APIs ---
resource "google_project_service" "svc" {
  for_each = toset(["container.googleapis.com", "artifactregistry.googleapis.com",
                    "secretmanager.googleapis.com", "compute.googleapis.com"])
  service            = each.value
  disable_on_destroy = false
}

# --- VPC (GCP's VCN equivalent) ---
resource "google_compute_network" "vpc" {
  name                    = "merit-aid-vpc"
  auto_create_subnetworks = false
}
resource "google_compute_subnetwork" "subnet" {
  name          = "merit-aid-subnet"
  ip_cidr_range = "10.10.0.0/16"
  region        = var.region
  network       = google_compute_network.vpc.id
}

# --- Artifact Registry (Docker images) ---
resource "google_artifact_registry_repository" "repo" {
  location      = var.region
  repository_id = "merit-aid"
  format        = "DOCKER"
  depends_on    = [google_project_service.svc]
}

# --- GKE cluster: small, Spot nodes, minimal count (cost-optimized) ---
resource "google_container_cluster" "gke" {
  name       = var.cluster_name
  location   = var.zone
  network    = google_compute_network.vpc.id
  subnetwork = google_compute_subnetwork.subnet.id
  remove_default_node_pool = true
  initial_node_count       = 1
  deletion_protection      = false
  depends_on = [google_project_service.svc]
}
resource "google_container_node_pool" "nodes" {
  name       = "primary"
  cluster    = google_container_cluster.gke.id
  location   = var.zone
  node_count = 2
  node_config {
    machine_type = "e2-small"   # cheap
    spot         = true          # preemptible-class pricing
    oauth_scopes = ["https://www.googleapis.com/auth/cloud-platform"]
  }
}

# --- Cloud Storage bucket for the 8 IPEDS CSVs ---
resource "google_storage_bucket" "data" {
  name                        = var.bucket_name
  location                    = var.region
  uniform_bucket_level_access = true
  force_destroy               = true
}
