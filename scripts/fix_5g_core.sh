#!/usr/bin/env bash
# Fix script for 5G Core Network issues
# This script addresses SCTP and TUN/TAP device requirements

set -e

echo "=== 5G Core Network Fix Script ==="
echo ""

# Check if running as root for kernel module loading
if [ "$EUID" -ne 0 ]; then 
    echo "⚠️  WARNING: This script needs root privileges to load kernel modules."
    echo "   Please run with: sudo $0"
    exit 1
fi

echo "[1/3] Loading SCTP kernel module..."
if lsmod | grep -q sctp; then
    echo "✅ SCTP module already loaded"
else
    if modprobe sctp 2>/dev/null; then
        echo "✅ SCTP module loaded successfully"
    else
        echo "❌ ERROR: Failed to load SCTP module"
        echo "   Your kernel may not have SCTP support compiled."
        echo "   Install it with: sudo pacman -S linux-headers (Arch) or sudo apt install linux-modules-extra-$(uname -r) (Ubuntu)"
        exit 1
    fi
fi

echo ""
echo "[2/3] Ensuring /dev/net/tun is available..."
if [ -c /dev/net/tun ]; then
    echo "✅ /dev/net/tun exists"
else
    echo "Creating /dev/net/tun..."
    mkdir -p /dev/net
    mknod /dev/net/tun c 10 200
    chmod 666 /dev/net/tun
    echo "✅ /dev/net/tun created"
fi

echo ""
echo "[3/3] Making kernel modules persistent across reboots..."
if ! grep -q "^sctp$" /etc/modules-load.d/5g-core.conf 2>/dev/null; then
    echo "sctp" > /etc/modules-load.d/5g-core.conf
    echo "✅ SCTP module will load on boot"
else
    echo "✅ SCTP module already configured for boot"
fi

echo ""
echo "═══════════════════════════════════════════════"
echo "  ✅ 5G Core prerequisites fixed!"
echo "═══════════════════════════════════════════════"
echo ""
echo "Now restart the 5G core pods:"
echo "  kubectl -n nexslice delete pod -l app.kubernetes.io/name=oai-amf"
echo "  kubectl -n nexslice delete pod -l app.kubernetes.io/name=oai-upf"
echo ""
