# Cheapest-viable GCP footprint for a student project.
# Values live in terraform.tfvars, which Terraform auto-loads: `terraform init &&
# terraform plan`. See DEPLOYMENT.md for the full cycle, including teardown.
terraform {
  required_version = ">= 1.5"
  required_providers {
    # Pinned to a major version that exists. Written against 5.x; 6.x renamed
    # nothing this config uses, so the constraint allows both and `terraform
    # providers lock` records what was actually applied.
    google = { source = "hashicorp/google", version = ">= 5.0, < 7.0" }
  }
}
provider "google" {
  project = var.project_id
  region  = var.region
}

# --- APIs ---
# secretmanager.googleapis.com is deliberately absent. It was here for the RAG
# panel's ANTHROPIC_API_KEY, and that feature was removed in Phase 3.5 because its
# only data source was generated text -- so the deploy path has no secret at all now.
# Enabling an API nothing uses is a surface with no purpose.
resource "google_project_service" "svc" {
  for_each = toset(["container.googleapis.com", "artifactregistry.googleapis.com",
                    "compute.googleapis.com", "storage.googleapis.com"])
  service            = each.value
  disable_on_destroy = false
}

# --- VPC (GCP's VCN equivalent) ---
resource "google_compute_network" "vpc" {
  name                    = "merit-aid-vpc"
  auto_create_subnetworks = false

  # This depends_on is not decoration. Without it the first apply against a fresh
  # project fails here with "Compute Engine API has not been used in project ...
  # before or it is disabled": Terraform sees no reference between this resource and
  # the API-enablement resources, so it creates the network in parallel with them.
  # Verified by hitting it on 2026-11-20.
  depends_on = [google_project_service.svc]
}
resource "google_compute_subnetwork" "subnet" {
  name          = "merit-aid-subnet"
  ip_cidr_range = "10.10.0.0/16"
  region        = var.region
  network       = google_compute_network.vpc.id

  # Secondary ranges for pods and services. These are what make the cluster
  # VPC-native, which is the precondition for container-native load balancing --
  # without them the `cloud.google.com/neg` annotation on a Service is rejected and
  # the Ingress falls back to probing a node port, which is the recorded 502.
  secondary_ip_range {
    range_name    = "pods"
    ip_cidr_range = "10.20.0.0/16"
  }
  secondary_ip_range {
    range_name    = "services"
    ip_cidr_range = "10.30.0.0/20"
  }
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

  ip_allocation_policy {
    cluster_secondary_range_name  = "pods"
    services_secondary_range_name = "services"
  }

  depends_on = [google_project_service.svc]
}
resource "google_container_node_pool" "nodes" {
  name       = "primary"
  cluster    = google_container_cluster.gke.id
  location   = var.zone
  node_count = 2
  node_config {
    # e2-medium rather than e2-small, decided from measurements taken on
    # 2026-11-20 rather than from the machine names.
    #
    # What actually happened: with the original 250m CPU / 512Mi requests, both
    # second replicas sat Pending on an e2-small pool -- "0/2 nodes are available:
    # 2 Insufficient memory" -- because an e2-small offers 1.33 GiB allocatable and
    # GKE's own system DaemonSets already request ~810 MiB of it per node. Moving
    # to e2-medium cleared memory and exposed the real binding constraint: a
    # shared-core E2 node reports only 940m allocatable CPU whatever its size, and
    # system pods request ~680m of that, so the 250m request still did not fit
    # alongside anti-affinity.
    #
    # The root cause was the requests, not the nodes: `kubectl top` shows the
    # backend using 3m CPU and 81Mi. They are now set from that measurement
    # (deploy/k8s/backend.yaml), which would also fit on e2-small -- but only with
    # about 250 MiB of headroom on a 2 GiB node whose pods may burst to 768Mi, so
    # the extra room is worth roughly $14/month across two Spot nodes.
    machine_type = "e2-medium"
    spot         = true          # preemptible-class pricing
    oauth_scopes = ["https://www.googleapis.com/auth/cloud-platform"]
  }
}

# --- Cloud Storage bucket for the 6 IPEDS CSVs ---
# Six, not eight: there are six source files (HD2022, SFA2122, IC2022_AY, ADM2022,
# DRVADM2022, DRVGR2022). This bucket is the durable copy the backend's init
# container pulls from on every pod start, so it is also what makes a pod restart
# survivable -- see deploy/k8s/backend.yaml.
resource "google_storage_bucket" "data" {
  name                        = var.bucket_name
  location                    = var.region
  uniform_bucket_level_access = true
  force_destroy               = true
}
