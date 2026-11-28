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

**The manifests pin image DIGESTS, not tags** (since 2026-11-27), so pushing is not
enough — you must refresh the digest or `kubectl apply` will be a no-op that leaves the
old image running:

```bash
for img in backend frontend; do
  gcloud artifacts docker images describe $REG/$img:latest --format='value(image_summary.digest)'
done
# paste each sha256:... into the matching `image:` line in deploy/k8s/<img>.yaml
```

Why bother: with a mutable `:latest`, any pod restart — a Spot preemption, a node
upgrade, an OOM kill — pulls whatever was last pushed. That turns a half-finished image
on the registry into the running code at a moment nobody chose. One preemption has
already restarted a pod on this cluster.

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

## Monitoring

```bash
gcloud monitoring uptime list-configs          # two checks, both -> /api/health, 5 min
gcloud alpha monitoring policies list          # "merit-aid: site not answering"
```

| Check | Target | Covers |
|---|---|---|
| `merit-aid-health` | `http://136.81.186.158/api/health` | the pods, the NEGs, the HTTP forwarding rule |
| `merit-aid-https` | `https://merit-aid-finder.com/api/health`, **validate-ssl on** | all of the above *plus* DNS resolution and the certificate |

The second was added on 2026-11-28 with TLS, because the first is **structurally blind**
to everything the domain introduced: delete the A record or let the certificate fail to
renew and the IP check stays green while nobody can reach the site by name.

> **`--validate-ssl` defaults to false, which would have made that check pointless.**
> As first created it reported healthy over HTTPS without checking the certificate at
> all — so the one failure mode it was added for, an expired or invalid certificate,
> would not have tripped it. Caught by reading the stored config back rather than
> trusting the create:
> ```
> DISPLAY_NAME      HOST                  PATH         USE_SSL  VALIDATE_SSL
> merit-aid-https   merit-aid-finder.com  /api/health  True     (empty)
> ```
> Fixed with `gcloud monitoring uptime update <ID> --validate-ssl=true`. Note the
> `=true`: the bare `--validate-ssl` flag is rejected.

An incident opens when the check fails for five minutes, and the policy carries its own
runbook: check `kubectl get pods -o wide` first (a Spot preemption recreates the node,
which takes a couple of minutes), then `curl http://136.81.186.158/api/meta` — a 503
there names the missing dataset file, which means the init container could not reach the
bucket.

Proven, not assumed: a deliberately failing decoy check delivered an incident in ~300
seconds on 2026-11-27.

> **A health check must target a path under `/api/`.** nginx serves the SPA with
> `try_files $uri $uri/ /index.html`, so **every** path that is not `/api/*` returns
> 200 — including nonsense. A check on `/` or on a mistyped path is green even with the
> backend completely dead. This was a real bug in the first version of the check:
> ```
> /api/health      HTTP 200       /not-an-api-path   HTTP 200
> /api/nope        HTTP 404       /C:/anything       HTTP 200
> ```
> **Still true over HTTPS** — re-measured on the domain 2026-11-28:
> `https://merit-aid-finder.com/api/nope` → 404 but `/not-an-api-path` → 200. Adding
> TLS changed nothing about which paths discriminate.

Recreating the HTTPS check from scratch, if it is ever lost — **run this from PowerShell,
not Git Bash.** MSYS rewrites a leading-slash argument into a Windows path, which is how
the first check ended up watching `/C:/Program Files/Git/api/health`:

```powershell
gcloud monitoring uptime create "merit-aid-https" --resource-type=uptime-url `
  --resource-labels="host=merit-aid-finder.com,project_id=merit-aid-app" `
  --path="/api/health" --port=443 --protocol=https --period=5 --timeout=10
gcloud monitoring uptime update <ID> --validate-ssl=true
```

Quote the whole `--resource-labels` string. Unquoted, PowerShell splits it and gcloud
rejects it with "uptime_url check has malformed host".

### Who gets told

**An email channel exists as of 2026-11-28** — channel `15116863192913042102`, display
name `hasan`. **The address is deliberately not recorded in this repo**, which is public;
read it from the live config if you need it:

```bash
gcloud alpha monitoring channels describe 15116863192913042102 --format="value(labels.email_address)"
```

**There is ONE alert policy, and it covers both uptime checks.** Worth stating because
the check names invite the opposite assumption: there is no `merit-aid-health` policy and
no `merit-aid-https` policy. `6020692583677610040` is the only one, and its condition
filter carries **no `check_id` restriction** —

```
filter: resource.type = "uptime_url" AND metric.type = ".../uptime_check/check_passed"
groupByFields: [resource.label.host, metric.label.check_id]
```

— so it matches every uptime check in the project and, because it groups by check, raises
a **separate incident per check**. Attaching a channel to this one policy notifies on
both. Adding a check needs no policy change, which is also the trap: **a check that
cannot fail is silently covered by an alert that can never fire.**

To recreate the channel and attach it:

```bash
gcloud alpha monitoring channels create --display-name="hasan" --type=email   --channel-labels=email_address=YOU@example.com

gcloud alpha monitoring policies update 6020692583677610040   --add-notification-channels=projects/merit-aid-app/notificationChannels/<NEW_ID>
```

> **`--add-notification-channels`, never `--set-notification-channels`.** `--set`
> *replaces* the list, which would silently drop the Pub/Sub channel — and Pub/Sub is the
> only witness that lets anyone verify delivery without access to somebody's inbox.
> `--add` appends. `--clear` and `--remove` also exist; neither is wanted here.

**gcloud cannot verify a channel or send a test notification.** The subcommands are
`create`, `delete`, `describe`, `list`, `update` and `config` — there is no `verify` and
no send-test. "Send test notification" is **Console-only** (Monitoring → Alerting →
Notification channels → the row's ⋮ menu). So delivery has to be proven by causing a real
incident; see below.

**The API reports nothing about verification for an email channel.** `verificationStatus`
is absent from the create response and from `describe --format=json` entirely — not
`VERIFIED`, not `UNVERIFIED`, absent — so **configuration cannot tell you whether email
will arrive.** That is not a gap worth arguing with; it is a reason to test.

### Proving delivery (the only way, since there is no test-notification API)

Add a decoy uptime check on a path that genuinely fails. The policy matches every check
in the project, so the decoy trips it without touching the live site — `/api/nope`
returns a real 404 while `/` keeps serving.

```powershell
gcloud monitoring uptime create "merit-aid-decoy-delivery-test" --resource-type=uptime-url `
  --resource-labels="host=136.81.186.158,project_id=merit-aid-app" `
  --path="/api/nope" --port=80 --protocol=http --period=1 --timeout=10

# drain the subscription FIRST, or an old message looks like a new success
gcloud pubsub subscriptions pull merit-aid-alerts-sub --auto-ack --limit=10

# then poll for the incident
gcloud pubsub subscriptions pull merit-aid-alerts-sub --auto-ack --limit=1 --format="value(message.data)"

gcloud monitoring uptime delete "<DECOY_ID>" --quiet     # always clean up
```

**Measured 2026-11-28, with the email channel attached:** the incident arrived on
Pub/Sub after **~292 seconds** (Phase 10's run was ~300s, so this is reproducible), and
the payload named the decoy rather than the real checks:

```
policy_name    : merit-aid: site not answering
check_id       : merit-aid-decoy-delivery-test-FbTVeNGhksM
observed_value : 6.000          <- 6 probers failing, threshold > 1
state          : open
incident_id    : 0.ofjiep7k9nom
```

The email it generates carries this subject, which is what to search an inbox for:

```
[ALERT - No severity] Uptime check failing for 5 minutes on merit-aid-app
Uptime Check URL labels {project_id=merit-aid-app, host=136.81.186.158}
```

Independent confirmation the probers themselves agree, read from the Monitoring REST API
(there is no `gcloud monitoring time-series` subcommand, so this needs a bearer token and
`x-goog-user-project`):

```
merit-aid-decoy-delivery-test   136.81.186.158        pass=  0  FAIL=  9
merit-aid-health                136.81.186.158        pass= 81  FAIL=  0
merit-aid-https                 merit-aid-finder.com  pass= 81  FAIL=  0
```

`merit-aid-https` passing there is a second result worth keeping: it checks with
`validate-ssl=true`, so Google's own probers trust the certificate from six locations.

> **What this test can and cannot prove.** It proves the policy fired, that the payload
> identified the right check, and that the email channel was attached to the policy when
> it fired. It does **not** prove an email reached an inbox — Cloud Monitoring exposes no
> per-channel delivery status, and there is no monitoring-notification log in this project
> (`gcloud logging logs list` shows only GKE, audit and node logs). The last link in the
> chain has to be confirmed by the person who owns the mailbox, and Gmail does sometimes
> file these under spam.

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

**These are the billed figures, not a price-list estimate.** Hasan read
**Billing → Reports** for project `merit-aid-app`, grouped by SKU, on 2026-11-27. The
earlier version of this section was a catalog-derived model; it was wrong in both
directions and the real total is lower. What follows replaces it.

**Actual: $17.71 for 2026-11-01 → 11-27.** The cluster has existed since 2026-11-20,
so that is about 7 days — roughly **$2.53/day, ~$76/month** at this shape.

| SKU as billed | Cost | What it actually is |
|---|---|---|
| Balanced PD Capacity | **$4.54** | the two node **boot disks** — 100 GB pd-balanced each |
| Spot E2 Instance Core | $4.20 | 2 × e2-medium vCPU |
| LB Forwarding Rule Minimum Global | $4.07 | the load balancer's one HTTP rule |
| Spot E2 Instance RAM | $2.25 | 2 × e2-medium memory |
| Prometheus Samples Ingested | $1.83 | 30,422,607 samples from GKE's managed collection |
| External IP charge on a Spot VM | $0.82 | the **nodes'** own public IPs, not `merit-aid-ip` |
| GKE cluster management fee | **absent** | credited to zero — see below |
| Static Ip Charge | **absent** | does not bill while attached — see below |

### Three things the billing detail settled

**1. The zonal-cluster credit is applying. The open question is closed.** No
cluster-management SKU appears in the report at all. That is not a subtle inference: the
fee is $0.100/hour, the cluster has existed for roughly 170 hours, so it would be about
**$17 on its own** — which would have made the total around $35, not $17.71. The
$73/month line that dominated every previous estimate in this file is $0. The report also
shows **−$18.81 in savings**, the right magnitude for that credit; it is not decomposed
per SKU, so treat the *absence of the SKU* as the proof and the savings figure as
corroboration.

**2. The static IP does not bill while it is attached.** No "Static Ip Charge" line
exists. The catalog lists the SKU at $0.010/hour but does not say whether an address
serving a live forwarding rule is charged, and this file previously carried it as "up to
$7.30/month" for that reason. It is $0. The caveat in *Tearing it down* still stands,
because an address that is **reserved and idle** is the case that does bill.

**3. The $0.82 external-IP line is the nodes, not the site's address.** Verified
2026-11-28: `gcloud compute instances list` shows both nodes holding public addresses
(e.g. 35.254.57.66). Nothing needs them — traffic reaches the pods through the load
balancer's NEGs — so they are a cost and an exposed surface for no benefit. Removing them
means private nodes, which recreates the node pool.

### Two costs every earlier version of this table omitted

**Node boot disks are the single largest line, at $4.54.** Verified 2026-11-28:
`gcloud compute disks list` shows **2 × 100 GB pd-balanced**, which is GKE's default and
was never chosen. At roughly $0.10/GiB-month that is about **$20/month for 200 GB** to
hold a container image and 20.5 MiB of CSVs. Dropping `disk_size_gb` to 32 would cut
around $13/month — **the biggest saving available in this deployment, bigger than the
load balancer.** It is not done, because changing it recreates the node pool, and that
is not a thing to do in the week before a presentation. Do it after.

**Managed Prometheus bills per sample ingested: $1.83 for 30.4M samples.** This one is
worth watching because it is the only line that grows on its own. But it is **not** the
uptime check and alert policy added in Phase 10 — those are Cloud Monitoring, under its
own free tier. Verified 2026-11-28, the source is the cluster's own metric collection:

```
monitoringConfig.managedPrometheusConfig.enabled: true
enableComponents: SYSTEM_COMPONENTS, STORAGE, HPA, POD, DAEMONSET, DEPLOYMENT,
                  STATEFULSET, CADVISOR, KUBELET, DCGM, JOBSET
```

Eleven component groups, all on by default — including **DCGM** (GPU metrics) and
**JOBSET** on a cluster that has neither. The sample count scales with pods and with
elapsed time, so the lever is trimming that component list, not touching the alerting.
Left alone for now: it is a control-plane mutation for about $7/month, and the alerting
built on top of this cluster is what the demo relies on noticing a failure.

### Still not verified

Billed spend is readable **only** in the console. There is no billing export to
BigQuery, `bq` is broken on this machine (`python3.14: command not found`), and no
gcloud surface returns cost. Every figure above came from Hasan reading the console;
the attribution of each SKU to a resource is what was verified here with gcloud.

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
> `gcloud compute forwarding-rules list`, `gcloud compute target-http-proxies list` and
> now also `gcloud compute target-https-proxies list` and
> `gcloud compute ssl-certificates list` will show them. There are **two** forwarding
> rules since TLS was added (2026-11-28), and `kubectl delete -f deploy/k8s/` is what
> releases both, along with the Google-managed certificate the `ManagedCertificate`
> object owns.

**The DNS zone deliberately survives a destroy.** `google_dns_record_set.apex` is
Terraform-managed, so `terraform destroy` removes the A record — but the zone
`merit-aid-finder-com` is **not** a Terraform resource. Cloud Domains created it as part
of registering the domain, turned DNSSEC on, and delegated the registrar's nameservers to
it. Importing it would put a `terraform destroy` one command away from deleting the zone
out from under a registration that is paid for until 2027-11-27 and that this config
cannot re-delegate. After a destroy/apply cycle the record comes back pointing at the
same static address, because it reads `google_compute_global_address.ingress.address`
rather than a hardcoded IP.

**Redeploying later** is the same cycle: `terraform apply`, re-upload the CSVs, push the
images, `kubectl apply -f deploy/k8s/`. About **15–20 minutes**, most of it the cluster.

---

## Operational notes

- **A voluntary drain cannot take both replicas.** PodDisruptionBudgets
  (`deploy/k8s/pdb.yaml`, `minAvailable: 1`) make the Eviction API refuse the second
  eviction with a 429, which is what protects the service during a GKE node
  auto-upgrade. It does *not* protect against Spot preemption — that is involuntary and
  no budget can veto it; two replicas on two nodes is what covers that.
- **The backend runs as uid 1000, not root**, with all capabilities dropped. If you add
  a feature that needs to write to the container filesystem, it will fail — write to
  the mounted volume or add an explicit `emptyDir`.
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

## Domain + HTTPS

**Done 2026-11-28.** `merit-aid-finder.com` was registered through Cloud Domains on
2026-11-27 ($12.00/year, renews 2027-11-27) and now serves the app over TLS. The raw
`http://136.81.186.158/` path is **still live and still certificate-free**, deliberately:
it is the demo's guaranteed fallback and needs neither DNS nor a certificate to work.

### What owns what

| Piece | Where it lives | Why there |
|---|---|---|
| DNS zone `merit-aid-finder-com` | Cloud Domains created it; **not** in Terraform | part of the registration's lifecycle — DNSSEC on, registrar NS delegated to it. Importing it would put `terraform destroy` one command from deleting the zone under a paid registration this config cannot re-delegate. |
| Apex `A` record | `google_dns_record_set.apex` in `deploy/terraform/main.tf` | reads `google_compute_global_address.ingress.address`, so the name and the IP are one fact and cannot drift. A console-created record would be a second, silently stale copy. |
| Certificate | `deploy/k8s/certificate.yaml` (`ManagedCertificate`) | Google renews it; nothing to rotate by hand. |
| Attachment | `networking.gke.io/managed-certificates` on the Ingress | this annotation is what makes the LB grow an HTTPS target proxy and a 443 forwarding rule. |

### The sequence, and why it is this order

**Apex first, `www` second — not both at once.** A Google-managed certificate does not go
ACTIVE until *every* name on it validates by DNS lookup. Listing `www` before an A record
exists for it holds the whole certificate in PROVISIONING indefinitely, and the apex —
which does resolve — gets no TLS either. One name is one way to fail instead of two.

```bash
# 1. DNS. The record points at the Terraform-managed address, not a literal IP.
cd deploy/terraform && terraform plan -out=tfplan-dns && terraform apply tfplan-dns

# 2. Confirm it resolves PUBLICLY before asking for a certificate. Issuance is a DNS
#    lookup Google performs; a record only the authoritative server knows is not enough.
nslookup merit-aid-finder.com 8.8.8.8

# 3. Certificate + attachment. HTTP keeps serving the whole time.
kubectl apply -f deploy/k8s/certificate.yaml
kubectl apply -f deploy/k8s/ingress.yaml

# 4. Watch it. Do NOT trust the status field alone -- fetch the site.
kubectl get managedcertificate merit-aid-cert   -o custom-columns='STATUS:.status.certificateStatus,DOMAIN:.status.domainStatus'
curl -sS -o /dev/null -w '%{http_code}
' https://merit-aid-finder.com/api/health
```

**There is deliberately no HTTP→HTTPS redirect.** A redirect would route the guaranteed
fallback through the component most likely to not be ready. `kubernetes.io/ingress.allow-http`
is pinned to `"true"` on the Ingress so nobody removes port 80 by accident. If a redirect
is wanted later it is a `FrontendConfig` with `redirectToHttps`, and only after the
certificate has been serving long enough to trust.

### What issuance actually took

Measured on 2026-11-28, with the `ManagedCertificate` applied at **07:29:19 UTC** (t0):

| t | Event | Read from |
|---|---|---|
| t+0s | `ManagedCertificate` created; LB grows a 443 forwarding rule and HTTPS proxy | `kubectl apply` |
| **t+490s (8m10s)** | **`https://merit-aid-finder.com/api/health` returns 200** | `curl` |
| t+545s (9m05s) | Google reports the certificate ACTIVE | `gcloud compute ssl-certificates list` |
| t+675s (11m15s) | `kubectl get managedcertificate` **still** says `Provisioning` | `kubectl` |
| t+737s (12m17s) | the Kubernetes CRD finally flips to `Active` | `kubectl` |

**8 minutes, not the 15–60 the pre-work warned about.** The warning was not wrong to
exist — issuance can take far longer, and the cause is almost always DNS not resolving
publicly yet — but with the A record already live and verified against `8.8.8.8` before
the certificate was requested, it was fast.

> **The Kubernetes status field is the last thing to update, and it lied for minutes.**
> HTTPS served real traffic for **247 seconds — 4m07s** before
> `kubectl get managedcertificate` stopped reporting `Provisioning`, and Google's own API
> reported ACTIVE more than three minutes before Kubernetes did. Anything that waits on the CRD status
> would have reported the site broken while it was working. **Verify with a request, not
> a status field** — the same lesson as the health check that was green with a mangled
> path.

The certificate as served (read off the wire with Python's `ssl`, not from the resource):

```
TLS version : TLSv1.3        cipher : TLS_AES_256_GCM_SHA384
subject     : CN=merit-aid-finder.com
issuer      : Google Trust Services, CN=WR3
SAN         : ['merit-aid-finder.com']          <- apex only, as intended
notBefore   : Nov 28 06:36:06 2026 GMT          <- backdated ~53 min for clock skew
notAfter    : Jan 12 07:29:20 2027 GMT          <- 45 days; Google auto-renews
```

`notAfter` is exactly 45 days after t0, so the validity window is anchored to the moment
the resource was created. Renewal is Google's job and needs no action here — but a failed
renewal is silent, which is why `merit-aid-https` exists as an uptime check with
`--validate-ssl=true`.

### Two gotchas worth knowing

- **The certificate is free; a similarly-named product is not.** There is no SKU for a
  GKE `ManagedCertificate` in the Cloud Billing catalog (checked 2026-11-27).
  **Certificate Manager** is a different resource type at $0.10/cert/month and is not
  what this uses.
- **Renaming the `ManagedCertificate` silently detaches TLS.** The Ingress annotation is
  a name lookup, and a missing target is not an error on the Ingress. Rename in both
  files or neither.

### A certificate cannot cover a bare IP

This is why a domain was needed at all, rather than an assumption:

```
$ gcloud compute ssl-certificates create test-ip-cert --domains=136.81.186.158 --global
ERROR: Invalid value for field 'resource.managed.domains[0]': '136.81.186.158'.
       Invalid domain name specified.
```

### `www` is a separate name and does not exist yet

The registration covers the apex. `www.merit-aid-finder.com` is a subdomain that exists
only if someone creates a record for it — verified 2026-11-28, `nslookup` against 8.8.8.8
returns **NXDOMAIN**. To add it once the apex is trusted:

```bash
# an A record for www -> the same address, in main.tf alongside the apex, then either
# add "www.merit-aid-finder.com" to certificate.yaml's domains list (one cert, two
# names, both must validate) or leave it HTTP-only until it does.
```
