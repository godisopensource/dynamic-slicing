#!/bin/bash
# Demo script to create a UE, verify the UPF is created, then delete the UE and verify UPF deletion.
# Prerequisites: kubectl configured, curl, and Flask server running (e.g. ./start.sh)

if ! command -v jq &> /dev/null; then
    echo "jq is required to parse API JSON response. Please install it."
    exit 1
fi

if [ "$#" -lt 1 ]; then
    echo "Usage: $0 <ue_id>"
    exit 1
fi

UE_ID=$1
BASE_URL="http://localhost:5000"

echo "Creating UE $UE_ID via API..."
curl -s -X POST "$BASE_URL/add_pod" -o /dev/null

# The add_pod endpoint creates a UE with a new index; the API script doesn't allow explicit ID.
# For a controlled demo, we fetch the last created UE via /api/ue-count
COUNT_RESPONSE=$(curl -sf "$BASE_URL/api/ue-count")
if [ $? -ne 0 ] || [ -z "$COUNT_RESPONSE" ]; then
    echo "Unable to fetch UE count from $BASE_URL/api/ue-count. Is Flask running?"
    exit 1
fi

COUNT=$(echo "$COUNT_RESPONSE" | jq -r '.count // 0')
if [ -z "$COUNT" ] || [ "$COUNT" == "null" ]; then
    echo "Invalid /api/ue-count response: $COUNT_RESPONSE"
    exit 1
fi

if ! [[ "$COUNT" =~ ^[0-9]+$ ]]; then
    echo "Field 'count' is not numeric: $COUNT_RESPONSE"
    exit 1
fi

if [ "$COUNT" -eq 0 ]; then
    echo "No UE found after creation. Check Flask service."
    exit 1
fi

echo "Last created UE: $COUNT (checking UPF upf-ue$COUNT)"

echo "Waiting 3s for K8s resources..."
sleep 3

# Check if kubectl can talk to a cluster
if kubectl version --client >/dev/null 2>&1 && kubectl cluster-info >/dev/null 2>&1; then
    echo "K8s verification: cluster accessible, showing resources..."
    kubectl get deployment "upf-ue$COUNT" -n nexslice --ignore-not-found
    kubectl get svc "upf-ue$COUNT" -n nexslice --ignore-not-found
else
    echo "No Kubernetes cluster accessible via kubectl: skipping K8s checks."
fi

read -p "Press Enter to delete UE and UPF..." dummy

# Delete via remove_pod endpoint
curl -s -X POST "$BASE_URL/remove_pod/$COUNT" -o /dev/null

sleep 2

echo "Verification after deletion:"
if kubectl version --client >/dev/null 2>&1 && kubectl cluster-info >/dev/null 2>&1; then
    kubectl get deployment "upf-ue$COUNT" -n nexslice --ignore-not-found
    kubectl get svc "upf-ue$COUNT" -n nexslice --ignore-not-found
else
    echo "No Kubernetes cluster accessible via kubectl: skipping K8s checks."
fi

echo "Demo finished."
