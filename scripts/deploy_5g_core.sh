#!/usr/bin/env fish
# Deploy OAI 5G Core Network using Helm charts from AIDY-F2N/NexSlice repo
# This script clones the NexSlice repo (if needed) and deploys the 5G core

set NEXSLICE_REPO "https://github.com/AIDY-F2N/NexSlice.git"
set NEXSLICE_BRANCH "main"
set NEXSLICE_DIR "/tmp/NexSlice"
set NAMESPACE "nexslice"

echo "=== NexSlice 5G Core Deployment Script ==="

# Check if kubectl is available
if not command -v kubectl &> /dev/null
    echo "ERROR: kubectl not found. Please install kubectl."
    exit 1
end

# Check if helm is available
if not command -v helm &> /dev/null
    echo "ERROR: helm not found. Please install helm."
    exit 1
end

# Create namespace if it doesn't exist
echo "Creating namespace $NAMESPACE (if not exists)..."
kubectl create namespace $NAMESPACE --dry-run=client -o yaml | kubectl apply -f -

# Clone NexSlice repo if not already present
if not test -d $NEXSLICE_DIR
    echo "Cloning NexSlice repository..."
    git clone --branch $NEXSLICE_BRANCH --depth 1 $NEXSLICE_REPO $NEXSLICE_DIR
else
    echo "NexSlice repo already present at $NEXSLICE_DIR"
end

# Navigate to the 5g_core/oai-5g-advance directory
if not test -d $NEXSLICE_DIR/5g_core/oai-5g-advance
    echo "ERROR: 5g_core/oai-5g-advance not found in $NEXSLICE_DIR"
    exit 1
end

pushd $NEXSLICE_DIR/5g_core/oai-5g-advance

# Update helm dependencies
echo "Updating Helm dependencies..."
helm dependency update .

# Install the 5G core
echo "Deploying 5G core network (AMF, SMF, NRF, UDM, UDR, AUSF, NSSF, UPF, MySQL)..."
helm install 5gc . -n $NAMESPACE

popd

echo ""
echo "=== 5G Core deployment initiated ==="
echo "Check status with: kubectl get pods -n $NAMESPACE"
echo "Wait for all pods to be Running before deploying UEs/UPFs."
