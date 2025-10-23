Design: Dynamic UPF per UE (NexSlice POC)

Goal
----
Automatically create a UPF per UE when the UE connects to the gNB and delete it when the UE disconnects. SMF remains static.

Approach
--------
Start with a simple controller implemented inside the Flask service (fast POC). This controller will:
- create a UPF Deployment+Service named `upf-ue<id>` when an UE is created
- delete `upf-ue<id>` when the UE disconnects

Data shapes
-----------
- UE id: integer (from generated UE configs; used as suffix)
- UPF resource names: `upf-ue<id>`
- Labels: `app: upf`, `ue-id: "<id>"`

Kubernetes objects
------------------
- Deployment `upf-ue<id>`
  - container ports: 2152 (gtp-u), 8805 (pfcp) UDP by default
  - image configurable via `UPF_IMAGE` env var
- Service `upf-ue<id>` ClusterIP

RBAC
----
ServiceAccount `nexslice-controller` (namespace: `nexslice`) with Role granting:
- pods, services, configmaps (get/list/watch/create/update/patch/delete)
- deployments in apps API group (same verbs)

Lifecycle
---------
- On UE creation (API /add_pod or bulk create):
  1) create ConfigMap and Pod for UE
  2) create UPF Deployment+Service
- On UE deletion (/remove_pod/<id>):
  1) delete UE Pod and ConfigMap
  2) delete UPF Deployment and Service

Edge cases
----------
- Concurrent creation of two identical UE ids (guard by using auto-increment logic already present)
- Partial failures: if UPF creation fails, log and allow manual retry. For production, use a reconciler with retries.
- Name collisions: use `ue-id` label and consistent naming convention.

Testing / Demo
--------------
- Manual: `scripts/demo.sh` creates an UE and checks `kubectl get deployment upf-ue<N> -n nexslice` and service.
- Automated: small Python test that calls the Flask endpoints and uses the Kubernetes client API to assert resource presence/absence.

Next steps
----------
- Add RBAC manifests (done: `k8s/rbac-nexslice.yaml`)
- Add automated tests harness
- Optionally, implement a proper operator (Kopf or Go operator) for reconciliation and robustness
