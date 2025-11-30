# 5G Core Network Troubleshooting Guide

## Issue: 5G Core Pods Not Starting

### Root Causes Identified

1. **Service IP Routing Issues (FIXED)**
   - **Problem**: K3s ClusterIP services were not routing traffic properly to pods
   - **Solution**: Changed services to headless mode (`clusterIP: None`) in custom values
   - **Status**: ✅ RESOLVED

2. **SCTP Protocol Not Supported (CRITICAL)**
   - **Problem**: AMF pod crashes with "Socket: Protocol not supported:93"
   - **Root Cause**: SCTP kernel module not loaded
   - **Required For**: AMF N2 interface (gNB-AMF communication via SCTP)
   
3. **TUN/TAP Device Access (CRITICAL)**
   - **Problem**: UPF pods crash with "Cannot find device tun0"
   - **Root Cause**: Missing /dev/net/tun device or insufficient permissions
   - **Required For**: UPF user plane tunneling

## Solutions

### Solution 1: Install and Load SCTP Module (RECOMMENDED)

#### For Arch Linux / Parch Linux:
```bash
# SCTP should be included in the kernel
# Check if module exists
ls /lib/modules/$(uname -r)/kernel/net/sctp/

# If not, install kernel modules
sudo pacman -S linux-headers

# Load SCTP module
sudo modprobe sctp

# Verify
lsmod | grep sctp

# Make persistent across reboots
echo "sctp" | sudo tee /etc/modules-load.d/5g-core.conf
```

#### For Ubuntu/Debian:
```bash
# Install SCTP support
sudo apt-get install -y libsctp-dev lksctp-tools linux-modules-extra-$(uname -r)

# Load module
sudo modprobe sctp

# Make persistent
echo "sctp" | sudo tee -a /etc/modules
```

#### Alternative: Use our fix script
```bash
sudo ./scripts/fix_5g_core.sh
```

### Solution 2: Fix TUN/TAP Device

```bash
# Ensure TUN device exists
sudo mkdir -p /dev/net
sudo mknod /dev/net/tun c 10 200
sudo chmod 666 /dev/net/tun
```

### Solution 3: Redeploy 5G Core with Fixed Configuration

After loading SCTP module and fixing TUN device:

```bash
# Uninstall current deployment
helm -n nexslice uninstall 5gc

# Redeploy with custom values
cd /tmp/NexSlice/5g_core/oai-5g-advance
helm install 5gc . -n nexslice -f /tmp/oai-5g-custom-values.yaml

# Wait for pods to be ready
kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=oai-nrf -n nexslice --timeout=120s
kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=oai-amf -n nexslice --timeout=300s
```

## Current Status

### Working Components:
- ✅ NRF (Network Repository Function) - Both instances running
- ✅ NSSF (Network Slice Selection Function)
- ✅ AUSF (Authentication Server Function)
- ✅ UDM (Unified Data Management)
- ✅ UDR (Unified Data Repository)  
- ✅ SMF (Session Management Function) - All 3 instances
- ✅ LMF (Location Management Function)
- ✅ MySQL database

### Components Needing Fix:
- ❌ AMF (Access and Mobility Management Function) - Needs SCTP support
- ❌ UPF (User Plane Function) - All 3 instances need TUN/TAP access
- ⚠️ UERANSIM gNB - Cannot connect without working AMF

## Quick Fix Commands

```bash
# 1. Load required kernel modules
sudo modprobe sctp
sudo modprobe tun

# 2. Verify modules loaded
lsmod | grep -E "sctp|tun"

# 3. Restart failing pods
kubectl -n nexslice delete pod -l app.kubernetes.io/name=oai-amf
kubectl -n nexslice delete pod -l app.kubernetes.io/name=oai-upf

# 4. Check pod status
kubectl get pods -n nexslice -w
```

## Verification

```bash
# Check AMF logs for successful SCTP initialization
kubectl -n nexslice logs -l app.kubernetes.io/name=oai-amf --tail=50

# Should see:
# "[sctp] [info] Create pthread to receive SCTP message"
# WITHOUT "Protocol not supported" error

# Check UPF logs
kubectl -n nexslice logs -l app.kubernetes.io/name=oai-upf --tail=50

# Should see:
# "[upf_n3] [start] Started"
# WITHOUT "Cannot find device tun0" error
```

## Next Steps After Fix

Once all 5GC components are running:

1. Deploy or restart UERANSIM gNB:
   ```bash
   kubectl -n nexslice delete pod ueransim-gnb
   ```

2. Verify gNB connects to AMF:
   ```bash
   kubectl -n nexslice logs ueransim-gnb
   # Should see successful N2 connection to AMF
   ```

3. Start the NexSlice application:
   ```bash
   ./start.sh
   ```

## Additional Notes

- The custom values file at `/tmp/oai-5g-custom-values.yaml` uses headless services which resolve directly to pod IPs, avoiding K3s service proxy issues
- The timeout for init containers has been increased from 1s to 5s
- All components use HTTP/2 with prior knowledge for NRF communication
