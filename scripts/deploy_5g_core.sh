#!/bin/bash
# Deploy OAI 5G Core Network using Helm charts from AIDY-F2N/NexSlice repo
# This script clones the NexSlice repo (if needed) and deploys the 5G core

NEXSLICE_REPO="https://github.com/AIDY-F2N/NexSlice.git"
NEXSLICE_BRANCH="main"
NEXSLICE_DIR="/tmp/NexSlice"
NAMESPACE="nexslice"

echo "=== NexSlice 5G Core Deployment Script ==="

# Check if kubectl is available
if ! command -v kubectl &> /dev/null; then
    echo "ERROR: kubectl not found. Please install kubectl."
    exit 1
fi

# Check if helm is available
if ! command -v helm &> /dev/null; then
    echo "ERROR: helm not found. Please install helm."
    exit 1
fi

# Create namespace if it doesn't exist
echo "Creating namespace $NAMESPACE (if not exists)..."
kubectl create namespace $NAMESPACE --dry-run=client -o yaml | kubectl apply -f -

# Clone NexSlice repo if not already present
if [ ! -d "$NEXSLICE_DIR" ]; then
    echo "Cloning NexSlice repository..."
    git clone --branch $NEXSLICE_BRANCH --depth 1 $NEXSLICE_REPO $NEXSLICE_DIR
else
    echo "NexSlice repo already present at $NEXSLICE_DIR"
fi

# Navigate to the 5g_core/oai-5g-advance directory
if [ ! -d "$NEXSLICE_DIR/5g_core/oai-5g-advance" ]; then
    echo "ERROR: 5g_core/oai-5g-advance not found in $NEXSLICE_DIR"
    exit 1
fi

pushd "$NEXSLICE_DIR/5g_core/oai-5g-advance" > /dev/null

# Update helm dependencies
echo "Updating Helm dependencies..."
helm dependency update .

# Install the 5G core
echo "Deploying 5G core network (AMF, SMF, NRF, UDM, UDR, AUSF, NSSF, UPF, MySQL)..."
helm install 5gc . -n $NAMESPACE

popd > /dev/null

echo ""
echo "=== 5G Core deployment initiated ==="
echo "Check status with: kubectl get pods -n $NAMESPACE"
echo "Wait for all pods to be Running before deploying UEs/UPFs."
