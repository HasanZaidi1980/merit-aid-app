variable "project_id" {
  type        = string
  description = "Your GCP project ID"
}
variable "region" {
  type    = string
  default = "us-central1"
}
variable "zone" {
  type    = string
  default = "us-central1-a"
}
variable "cluster_name" {
  type    = string
  default = "merit-aid-cluster"
}
variable "bucket_name" {
  type        = string
  description = "Globally-unique Cloud Storage bucket for the IPEDS CSVs"
}
