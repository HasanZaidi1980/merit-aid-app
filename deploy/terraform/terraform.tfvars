# Concrete values for this project. Terraform auto-loads this file, so
# `terraform apply` does not need -var flags.
#
# The project already exists and billing is linked to it -- verified 2026-11-20 with
# `gcloud projects describe` and `gcloud billing projects describe`. Terraform must
# not try to create the project; it only creates what is inside it.
#
# The bucket does NOT exist yet (verified: `gcloud storage buckets list` returns
# nothing for this project). Terraform creates it, and the six CSVs are uploaded
# afterwards -- DEPLOYMENT.md step 2.

project_id   = "merit-aid-app"
region       = "us-central1"
zone         = "us-central1-a"
cluster_name = "merit-aid-cluster"
bucket_name  = "merit-aid-ipeds-2026"
