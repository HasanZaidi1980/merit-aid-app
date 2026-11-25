output "cluster_name" { value = google_container_cluster.gke.name }
output "region"       { value = var.region }
output "bucket"       { value = google_storage_bucket.data.name }
output "registry"     { value = "${var.region}-docker.pkg.dev/${var.project_id}/merit-aid" }
# The address the site is reachable at. Static, so it survives destroy/apply.
output "ingress_ip" { value = google_compute_global_address.ingress.address }
