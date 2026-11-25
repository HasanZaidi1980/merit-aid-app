# Deploying to GCP

Static frontend + FastAPI backend on **GKE**, behind a **Google Cloud Load Balancer**,
images in **Artifact Registry**, the six IPEDS CSVs in **Cloud Storage**. Cost-optimised:
one zonal cluster, two Spot nodes.

Everything below was run end to end on **2026-11-20**, and the figures and failure modes
in it are what actually happened, not what the manifests imply.

---

## 0. What you need installed

| Tool | Version used | Notes |
|---|---|---|
| `gcloud` | 583.0.0 | Plus the GKE auth plugin: `gcloud components install gke-gcloud-auth-plugin`. Without it `kubectl` cannot authenticate to the cluster at all. |
| `kubectl` | v1.34.1 | Ships with Docker Desktop, or `gcloud components install kubectl`. |
| `terraform` | 1.17.2 | Not installed by default on this machine. Download the Windows zip from `releases.hashicorp.com`, check it against the published `SHA256SUMS`, and unzip it somewhere on `PATH` (here: `C:\Users\<you>\tools\terraform`). No admin rights needed. |
| `docker` | 29.5.3 | Docker Desktop must actually be **running** — the CLI is on `PATH` whether or not the daemon is up, and `docker build` fails with a pipe error if it isn't. |

Then authenticate and point gcloud at the right project:

```bash
gcloud auth login                       # browser flow, once
gcloud auth application-default login   # Terraform reads these credentials
gcloud config set project merit-aid-app
```

> `gcloud config set project` is global. If you work across projects, remember this
> machine was previously set to `healthbuddy-prod-507317` — set it back when you're done.

## The values this deploys with

```
project_id   = "merit-aid-app"
bucket_name  = "merit-aid-ipeds-2026"
region       = "us-central1"
zone         = "us-central1-a"
cluster_name = "merit-aid-cluster"
```

They live in `deploy/terraform/terraform.tfvars`, which Terraform auto-loads. The project
already exists with billing linked; Terraform creates everything *inside* it and never the
project itself.

---

## 1. Provision the infrastructure

```bash
cd deploy/terraform
terraform init
terraform plan -out=tfplan     # read it
terraform apply tfplan
```

Creates: 4 enabled APIs, a VPC + subnet (with the secondary ranges that make the cluster
VPC-native), the GKE cluster, a 2-node Spot pool, an Artifact Registry repo, the GCS
bucket and the **static external IP**. **About 10 minutes**, nearly all of it the cluster
(8m35s observed).

> **The IP is static, and that is load-bearing.** The Ingress claims
> `merit-aid-ip` by name (`kubernetes.io/ingress.global-static-ip-name`), so a
> redeploy comes back on the same address instead of a new one. It is a
> `google_compute_global_address` — **global**, because a GKE Ingress creates a global
> external Application Load Balancer and a regional address cannot serve a global
> forwarding rule. On 2026-11-25 the existing ephemeral address was promoted in place
> rather than replaced, so the live URL never changed:
>
> ```bash
> gcloud compute addresses create merit-aid-ip --global --addresses=136.81.186.158
> terraform import google_compute_global_address.ingress merit-aid-ip
> terraform plan      # No changes. Your infrastructure matches the configuration.
> ```

> **First-apply trap, now fixed in `main.tf`:** on a project where the Compute API has
> never been used, the VPC is created in parallel with the API-enablement resources and
> fails with *"Compute Engine API has not been used in project … before or it is
> disabled"*. The `depends_on = [google_project_service.svc]` on the network is what
> prevents it. If you hit it anyway (API enablement propagates for a minute or two), just
> run `terraform apply` again — the resources that already exist are untouched.

## 2. Upload the six IPEDS CSVs

```bash
cd ../..
gcloud storage cp backend/data/*.csv gs://merit-aid-ipeds-2026/
gcloud storage ls -l gs://merit-aid-ipeds-2026/    # expect 6 objects, ~20.5 MiB
```

The bucket is the only durable copy of the dataset in the cloud. `backend/data/` is
gitignored and `backend/.dockerignore` excludes `data/`, so the data is in neither the
repo nor the image — by design. See **How the data reaches the pods** below.

## 3. Build and push the images

```bash
REG=us-central1-docker.pkg.dev/merit-aid-app/merit-aid
SHA=$(git rev-parse --short HEAD)
gcloud auth configure-docker us-central1-docker.pkg.dev
docker build --platform linux/amd64 -t $REG/backend:latest  -t $REG/backend:$SHA  ./backend
docker build --platform linux/amd64 -t $REG/frontend:latest -t $REG/frontend:$SHA ./frontend
docker push $REG/backend:latest  && docker push $REG/backend:$SHA
docker push $REG/frontend:latest && docker push $REG/frontend:$SHA
```

`--platform linux/amd64` matters: the nodes are x86, and an image built on an ARM machine
will pull fine and then crash-loop with an exec format error.

The manifests reference `:latest`; the commit tag is pushed alongside it so you can always
tell which build is live (`gcloud artifacts docker images list $REG --include-tags`).

*(There is no step here for an API key. The RAG panel was removed in Phase 3.5, so this
deploy has no secret, no Secret Manager dependency and no `secretKeyRef` anywhere.)*

## 4. Deploy to the cluster

```bash
gcloud container clusters get-credentials merit-aid-cluster --zone us-central1-a
kubectl apply -f deploy/k8s/
kubectl rollout status deploy/backend
kubectl get ingress merit-aid -w     # wait for ADDRESS; 5-10 minutes on first create
```

No placeholder substitution is needed any more — the manifests carry the real registry
path and bucket name.

---

## How the data reaches the pods

The image ships no CSVs, so something has to put them on the pod. Three routes were
considered; the one implemented is the **init container**:

| Route | Why not / why yes |
|---|---|
| Bake the CSVs into the image | Simplest, and the registry *is* private (its IAM policy has no bindings at all — only project-level access). Rejected anyway: updating the data would mean rebuilding and repushing the image, and `backend/.dockerignore` deliberately excludes `data/` so that a stray local dataset can never end up in a pushed image. |
| GCS CSI driver (gcsfuse mount) | Workable, but it needs Workload Identity plus the addon, and it puts a FUSE filesystem under pandas for a dataset small enough to copy in seconds. |
| **Init container copying from GCS** ✅ | Each pod copies the six files from `gs://merit-aid-ipeds-2026/` into an `emptyDir` at start. 21 MB, about a second at the observed 24.9 MiB/s. |

**Why `emptyDir` is still correct here, and a PVC is not.** A ReadWriteOnce persistent disk
attaches to one node at a time, which would make the two replicas mutually exclusive — the
second pod would sit Pending forever. The bucket is the durable copy; each pod keeps a
private scratch copy. A pod restart therefore cannot lose the data, because the data is
re-fetched rather than remembered. The init container counts the files and exits non-zero
if it does not get exactly six, so a half-copied dataset fails loudly instead of serving a
short one.

Authentication is the node's own service account (`cloud-platform` scope), which is why no
key material appears anywhere in the manifests.

---

## Verifying a deploy

```bash
IP=$(kubectl get ingress merit-aid -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
curl -s http://$IP/api/health                       # {"ok":true}
curl -s "http://$IP/api/meta" | jq '.colleges_in_dataset, .net_price_min, .net_price_max'
curl -s "http://$IP/api/colleges?top_n=3" | jq '.colleges[] | {RANK, INSTNM, NET_PRICE_MID}'
```

Expect `1907`, `2200`, `63997` — the same structural targets the test suite pins. If the
dataset is missing or short, `/api/meta` answers **503** naming the file and the directory
rather than a 500 from inside numpy, so a broken data path is diagnosable from `curl`
alone, without shell access to the pod.

Two checks worth running after any change to the manifests:

```bash
kubectl get pods -o wide                 # both backend replicas on DIFFERENT nodes
kubectl delete pod -l app=backend --wait=false && kubectl rollout status deploy/backend
```

The second one is the real test of the data path: the replacement pod must come back
serving 1,907 colleges, which it can only do by re-fetching from the bucket.

---

## Cost

**What is billed, at list price** (SKU figures read from Google's Cloud Billing Catalog
API on 2026-11-20, not from a blog post):

| Item | SKU price | Per day | Per month (730h) |
|---|---|---|---|
| Zonal GKE cluster management fee | $0.100000 / hour | $2.40 | $73.00 |
| 2 × e2-medium Spot nodes | $0.012440 / vCPU-hr + $0.001666 / GiB-hr → $0.019104/node-hr | $0.92 | $27.90 |
| External Application Load Balancer | not read from the catalog API | ~$0.60 | ~$18 (unverified) |
| Static external IP | $0.010000 / hour (base "Static Ip Charge" SKU) | up to $0.24 | up to $7.30 |
| GCS storage (20.5 MiB) + Artifact Registry (~1 GB) | negligible | <$0.01 | ~$0.15 |

**Roughly $3.50–4.00 a day, $100–120 a month**, which is at the top of the original
$70–100 estimate. Two caveats on precision: the load-balancer line is the one figure not
taken from a primary source, and the static-IP SKU exists at $0.010/hour but Google
charges it differently for an address that is attached to a live forwarding rule than for
one sitting idle — the billing detail will show which applies here, since the address was
only reserved on 2026-11-25.

**The GKE free tier may cancel most of this.** Google gives one zonal cluster per billing
account a $74.40/month credit. No other GKE cluster exists in any project on this billing
account (checked across all 11 projects on 2026-11-20), so this cluster should be the one
that gets it — which would leave roughly $45–50/month. That is an expectation, not a
measurement: confirm it against the actual bill after 24–48 hours, in
**Billing → Reports**, filtered to project `merit-aid-app`.

Charges accrue whether or not anybody visits the site.

---

## Tearing it down

**`terraform destroy` is what stops the charges.** It deletes the cluster, the nodes, the
load balancer, the bucket and the static IP — the resources stop existing, so they stop
billing.

> **Destroying releases the URL.** The static address is now managed by Terraform, so
> `terraform destroy` deletes it too and the next deploy comes back on a different IP.
> That is the right default: an idle reserved address keeps billing for nothing. If you
> want to keep `136.81.186.158` across a teardown — because it is written in the README
> and shared — take it out of Terraform's control first, then put it back on redeploy:
>
> ```bash
> cd deploy/terraform
> terraform state rm google_compute_global_address.ingress   # survives destroy
> terraform destroy
> # ...later, redeploying:
> terraform apply
> terraform import google_compute_global_address.ingress merit-aid-ip
> ```
>
> The address then bills on its own (see the cost table) while nothing is using it.

**Never switch the billing account off.** Five-plus projects share this billing account,
including `healthbuddy-prod`. Disabling billing affects every one of them and can break or
delete resources far outside this project. Teardown is `destroy`, never a billing change.

Run it in this order:

```bash
kubectl delete -f deploy/k8s/          # first: releases the load balancer
cd deploy/terraform && terraform destroy
```

The order matters. The Ingress owns a Google Cloud load balancer, forwarding rules and
health checks that live *outside* Kubernetes; if you destroy the cluster first, those
objects survive, keep billing, and block the VPC delete — Terraform then hangs for a long
time and eventually fails on a network that still has dependents. Deleting the Kubernetes
objects first lets the ingress controller clean up its own load balancer before the
cluster goes away. Give it a minute or two between the two commands.

> **Untested, deliberately.** This order is written from how the resources depend on each
> other, not from having run it: the stack is up for the demo and tearing it down to prove
> the teardown sequence would have meant rebuilding it afterwards. If `terraform destroy`
> does hang, the cause is almost always a leftover forwarding rule or target proxy —
> `gcloud compute forwarding-rules list` and `gcloud compute target-http-proxies list` will
> show them.

**Redeploying later** is the same cycle: `terraform apply`, re-upload the CSVs, push the
images, `kubectl apply -f deploy/k8s/`. About **15–20 minutes**, most of it the cluster.

---

## Operational notes

- **Spot nodes can be preempted at any time.** That is the whole reason for `replicas: 2`
  with *required* pod anti-affinity: the two backends must be on different nodes, or one
  preemption takes the service down. Verify with `kubectl get pods -o wide` after any
  change — if both land on one node, the second replica is buying nothing.
- **Rollouts use `maxSurge: 0`.** With required anti-affinity and exactly as many replicas
  as nodes, a surging pod has nowhere to be scheduled and the rollout deadlocks with the
  new pod Pending. Replacing rather than surging dips capacity to one replica for a few
  seconds per deploy.
- **Resource requests are measured, not guessed.** `kubectl top pod` shows the backend at
  3m CPU and 81Mi serving the real dataset. The requests are set from that with headroom
  (100m / 256Mi) and the limits allow bursting (1 CPU / 768Mi). The original 250m/512Mi
  were large enough to leave the second replica unschedulable on a shared-core node.
- **Shared-core E2 nodes report 940m allocatable CPU** whatever their memory size, and
  GKE's own system pods request about 680m of it. Budget node capacity from
  `kubectl describe node`, not from the machine type's advertised vCPUs.
- **A reserved IP must match the load balancer's scope.** Global ALB, global address.
  `gcloud compute forwarding-rules list --global` shows the rule; it appears under no
  region. Reserving a *regional* address for it would create a second, unusable IP and
  leave the live one ephemeral.
- **`ingressClassName: gce` does not work on GKE.** This cluster has no IngressClass
  objects at all (`kubectl get ingressclass` → *No resources found*), so the Ingress must
  carry the `kubernetes.io/ingress.class: "gce"` annotation that Kubernetes marks
  deprecated. With `ingressClassName` the Ingress is silently ignored: no address, and —
  the tell — no events whatsoever.

## Add a domain + HTTPS later (optional)

Point a domain's A record at the ingress IP, then add a `ManagedCertificate` and attach it
to the Ingress. Not needed for a demo — the raw load-balancer IP works.
