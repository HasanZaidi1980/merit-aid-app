# Deploying to GCP

Matches the live app's setup: static frontend + FastAPI backend on **GKE**, behind a
**Google Cloud Load Balancer**, images in **Artifact Registry**, data in **Cloud Storage**,
vector index on a **Persistent Disk**. Optimized for lowest cost (small e2-small Spot nodes).

## Prerequisites
`gcloud`, `kubectl`, `terraform`, and `docker` installed; a GCP project with billing on.

## 1. Provision infrastructure
```bash
cd deploy/terraform
terraform init
terraform apply -var project_id=YOUR_PROJECT -var bucket_name=YOUR_UNIQUE_BUCKET
```
This creates the VPC, GKE cluster, Artifact Registry repo, and the storage bucket.

## 2. Upload the 7 IPEDS CSVs (manual, once)
```bash
gcloud storage cp backend/data/*.csv gs://YOUR_UNIQUE_BUCKET/
```

## 3. Store the Anthropic API key as a Kubernetes Secret
```bash
gcloud container clusters get-credentials merit-aid-cluster --zone us-central1-a
kubectl create secret generic anthropic --from-literal=api-key=sk-ant-...
```

## 4. Build + push images
```bash
REG=us-central1-docker.pkg.dev/YOUR_PROJECT/merit-aid
gcloud auth configure-docker us-central1-docker.pkg.dev
docker build -t $REG/backend:latest ./backend  && docker push $REG/backend:latest
docker build -t $REG/frontend:latest ./frontend && docker push $REG/frontend:latest
```

## 5. Deploy
Replace `REGION`/`PROJECT_ID` in `deploy/k8s/*.yaml` with your values, then:
```bash
kubectl apply -f deploy/k8s/backend.yaml
kubectl apply -f deploy/k8s/frontend.yaml
kubectl apply -f deploy/k8s/ingress.yaml
kubectl get ingress merit-aid -w        # wait for the external IP
```
Open the IP in a browser. (Data note: the manifest mounts the CSVs via an emptyDir for
simplicity — for production, mount the GCS bucket with the CSI driver or init-copy the
files from `gs://YOUR_UNIQUE_BUCKET/` on pod start.)

## Tear it all down (stop billing!)
GKE + a load balancer bill continuously. When your demo is done:
```bash
kubectl delete -f deploy/k8s/            # remove the load balancer first
cd deploy/terraform && terraform destroy -var project_id=YOUR_PROJECT -var bucket_name=YOUR_UNIQUE_BUCKET
```

## Add a domain + HTTPS later (optional)
Point a domain's A-record at the ingress IP, then add a `ManagedCertificate` and attach it
to the ingress. Not needed for a demo — the raw load-balancer IP works, exactly like the
live app.
