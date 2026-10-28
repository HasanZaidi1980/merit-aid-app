# Concrete values for this project. Terraform auto-loads this file, so
# `terraform apply` no longer needs -var flags.
#
# NOTE: bucket_name was lowercased from "SOTCOTW123-merit-aid-bucket".
# Cloud Storage bucket names may not contain uppercase letters — the original
# would have been rejected at create time.

project_id   = "merit-aid-app"
region       = "us-central1"
zone         = "us-central1-a"
cluster_name = "merit-aid-cluster"
bucket_name  = "sotcotw123-merit-aid-bucket"
