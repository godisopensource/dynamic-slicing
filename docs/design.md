Design: Dynamic UPF per UE (NexSlice POC)

Goal
----
Automatically create a UPF per UE when the UE connects to the gNB and delete it when the UE disconnects. SMF remains static.

This POC corresponds to the **custom controller** recommended by the state-of-the-art: it reacts to UE connection/disconnection events and manages the lifecycle of per-UE UPFs in Kubernetes.

Architecture context
--------------------

- 5G core and slices are ideally managed declaratively via an operator such as `open5gs-operator` or a Helm-based stack (e.g. `towards5gs-helm`).
- Prometheus / Alertmanager and KEDA can be used to trigger scaling actions based on metrics (number of UEs per slice, N4 messages, UPF load, etc.).
- This project implements the *controller layer* that would be called by those components (or by a 5G core operator) via HTTP/webhooks.

Approach
--------

Start with a simple controller implemented inside the Flask service (fast POC). This controller will:
- create a UPF Deployment+Service named `upf-ue<id>` when an UE is created or connected,
- delete `upf-ue<id>` when the UE disconnects.

There are two types of entrypoints:

- **UI/demo endpoints** (`/add_pod`, `/remove_pod/<id>`): simulate a user adding/removing UEs and create/delete the corresponding UPF.
- **Webhook endpoints** (`/api/ue-connect`, `/api/ue-disconnect`): designed to be called by external systems (Alertmanager, 5G operator, etc.) to signal real UE events.

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

- On UE creation/connection (API `/add_pod`, bulk create, or webhook `/api/ue-connect`):
  1) create ConfigMap and Pod for UE,
  2) create UPF Deployment+Service.
- On UE deletion/disconnection (`/remove_pod/<id>` or webhook `/api/ue-disconnect`):
  1) delete UE Pod and ConfigMap,
  2) delete UPF Deployment and Service.

Edge cases
----------
- Concurrent creation of two identical UE ids (guard by using auto-increment logic already present)
- Partial failures: if UPF creation fails, log and allow manual retry. For production, use a reconciler with retries.
- Name collisions: use `ue-id` label and consistent naming convention.

Testing / Demo
--------------

- Manual: `scripts/demo.sh` creates an UE and checks `kubectl get deployment upf-ue<N> -n nexslice` and service.
- Automated: Python test (`tests/test_dynamic_upf.py`) that calls the Flask endpoints and uses the Kubernetes client API to assert resource presence/absence.

Next steps
----------

- Add RBAC manifests (done: `k8s/rbac-nexslice.yaml`).
- Enrich the automated test harness to cover the webhook endpoints (`/api/ue-connect` / `/api/ue-disconnect`).
- Optionally, implement a proper operator (Kopf or Go operator) that watches CRDs (e.g. UE or Slice resources) instead of being driven only by HTTP calls.
- Integrate with Prometheus / KEDA by exposing metrics and/or reacting to Alertmanager webhooks.
