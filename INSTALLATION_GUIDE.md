# NexSlice 5G Core Installation Guide

## ⚠️ CRITICAL: Manual Steps Required Before Starting

The 5G core network requires specific kernel modules that need root access to install.

### Step 1: Install Prerequisites (Run Once)

Execute the following commands with sudo:

```bash
# Install SCTP support package
sudo pacman -S --noconfirm lksctp-tools

# Load SCTP kernel module
sudo modprobe sctp

# Load TUN module (should already be loaded)
sudo modprobe tun

# Verify modules are loaded
lsmod | grep -E "sctp|tun"
```

### Step 2: Make Modules Persistent (Run Once)

```bash
# Create modules configuration
echo "sctp" | sudo tee /etc/modules-load.d/5g-core.conf
echo "tun" | sudo tee -a /etc/modules-load.d/5g-core.conf

# Ensure TUN device exists
sudo mkdir -p /dev/net
if [ ! -c /dev/net/tun ]; then
    sudo mknod /dev/net/tun c 10 200
    sudo chmod 666 /dev/net/tun
fi
```

### Step 3: Deploy 5G Core Network

```bash
# Uninstall any existing deployment
helm -n nexslice uninstall 5gc 2>/dev/null || true

# Deploy with fixed configuration
cd /tmp/NexSlice/5g_core/oai-5g-advance
helm install 5gc . -n nexslice -f /tmp/oai-5g-custom-values.yaml

# Wait for core components to be ready (2-3 minutes)
kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=oai-nrf -n nexslice --timeout=120s
echo "NRF ready, waiting for AMF..."
kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=oai-amf -n nexslice --timeout=300s
echo "AMF ready!"
```

### Step 4: Restart Dependent Pods

```bash
# Restart UERANSIM gNB to connect to the new AMF
kubectl -n nexslice delete pod ueransim-gnb 2>/dev/null || true

# Restart UE pods if they're in CrashLoopBackOff
kubectl -n nexslice delete pod -l app=upf-ue 2>/dev/null || true
```

### Step 5: Start NexSlice Application

```bash
# Run WITHOUT DEMO_MODE
./start.sh
```

## Verification

### Check 5G Core Status

```bash
# All these pods should be Running and Ready
kubectl get pods -n nexslice | grep oai-
```

Expected output:
```
oai-amf-xxx       1/1   Running   0   2m
oai-ausf-xxx      1/1   Running   0   2m
oai-lmf-xxx       1/1   Running   0   2m
oai-nrf-xxx       1/1   Running   0   2m
oai-nrf2-xxx      1/1   Running   0   2m
oai-nssf-xxx      1/1   Running   0   2m
oai-smf-xxx       1/1   Running   0   2m
oai-smf2-xxx      1/1   Running   0   2m
oai-smf3-xxx      1/1   Running   0   2m
oai-udm-xxx       1/1   Running   0   2m
oai-udr-xxx       1/1   Running   0   2m
oai-upf-xxx       1/1   Running   0   2m
oai-upf2-xxx      1/1   Running   0   2m
oai-upf3-xxx      1/1   Running   0   2m
```

### Check UERANSIM gNB Connection

```bash
kubectl -n nexslice logs ueransim-gnb --tail=20
```

Should see:
```
[SCTP connection established]
[GNB registered to AMF]
```

### Check AMF Logs

```bash
kubectl -n nexslice logs -l app.kubernetes.io/name=oai-amf --tail=30
```

Should NOT see "Protocol not supported" errors.

### Check UPF Logs

```bash
kubectl -n nexslice logs -l app.kubernetes.io/name=oai-upf --tail=30
```

Should NOT see "Cannot find device tun0" errors.

## Automated Installation Script

Alternatively, you can run our automated script (requires sudo):

```bash
sudo ./scripts/install_5g_prerequisites.sh
```

## Troubleshooting

See [docs/5G_CORE_TROUBLESHOOTING.md](docs/5G_CORE_TROUBLESHOOTING.md) for detailed troubleshooting information.

### Common Issues

1. **"Protocol not supported:93"** → SCTP module not loaded, run `sudo modprobe sctp`
2. **"Cannot find device tun0"** → TUN device missing, run `sudo modprobe tun`
3. **Pods stuck in Init state** → Check init container logs with `kubectl -n nexslice logs <pod> -c init`
4. **Services not reachable** → We use headless services (clusterIP: None) to avoid K3s routing issues

## What Was Fixed

### Issue 1: Service IP Routing (RESOLVED)
- **Problem**: K3s ClusterIP services (10.43.x.x) were timing out
- **Solution**: Changed to headless services that resolve directly to pod IPs (10.42.x.x)
- **File**: `/tmp/oai-5g-custom-values.yaml` with `clusterIpServiceIpAllocation: false`

### Issue 2: SCTP Support (REQUIRES MANUAL FIX)
- **Problem**: AMF needs SCTP protocol for N2 interface (gNB communication)
- **Solution**: Install lksctp-tools and load sctp kernel module
- **Commands**: See Step 1 above

### Issue 3: TUN/TAP Device (REQUIRES MANUAL FIX)  
- **Problem**: UPF needs /dev/net/tun for user plane tunneling
- **Solution**: Load tun module and ensure device exists
- **Commands**: See Step 2 above

## Next Steps

After the 5G core is fully operational:

1. Access NexSlice Web UI: http://localhost:5000
2. Create network slices via the API
3. Monitor UE traffic in Grafana: http://localhost:3000
4. Check metrics: http://localhost:9090 (Prometheus)

## Important Notes

- The 5G core MUST be running before starting the NexSlice Flask application
- Do NOT use DEMO_MODE=1 once prerequisites are installed
- The SCTP and TUN modules need to be loaded every boot (persistent configuration is set up in Step 2)
- This setup works with K3s on Arch/Parch Linux
