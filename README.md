# dynamic-slicing

Demo project for dynamic UPF creation per UE (NexSlice POC).

## Overview
This repository contains a small Flask-based tool that simulates UE creation (via UERANSIM pods) and demonstrates dynamic creation and deletion of a UPF per UE in Kubernetes. It's intended as a proof-of-concept to illustrate dynamic slicing: when a UE connects, an UPF is created for its slice; when the UE disconnects, the UPF is removed.

## Quickstart
Prerequisites:
- A Kubernetes cluster and a configured kubeconfig that points to it
- kubectl installed
- Python 3.11+ and pip

1. Install Python deps:

	pip install -r requirements.txt

2. Start the Flask app (from repo root):

	python -m src.main

3. Use the demo script to create an UE and verify UPF creation (the script will use kubectl):

	./scripts/demo.sh 1

## Files of interest
- `src/main.py` – Flask app that generates UE config, creates UE ConfigMap/Pod, and now creates/deletes a UPF Deployment+Service per UE.
- `scripts/demo.sh` – simple demo script that exercises add/remove UE flows and checks for the UPF resources via `kubectl`.

## Configuration
- The UPF image used by default is `free5gc/upf:latest`. To override it set the environment variable `UPF_IMAGE` before starting the Flask app.
- The number of replicas for a UPF Deployment can be controlled via `UPF_REPLICAS` env var.

## Notes & next steps
This is a minimal POC. For production-like behavior you should:
- Add proper RBAC (ServiceAccount, Role/ClusterRole, RoleBinding) if running as a Pod in-cluster.
- Harden error handling and add reconciliation (or implement a Kubernetes Operator) to ensure state remains correct after controller restarts.
- Replace the placeholder UPF image/arguments with the UPF you use in your core network (free5gc, bess-upf, etc.) and mount any needed config.

If you want, I can now:
- Wire automatic UPF creation into the UE creation endpoints (already implemented in the repo),
- Add RBAC manifests,
- Provide a small test harness that validates create/delete flows.
# dynamic-slicing