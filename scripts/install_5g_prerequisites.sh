#!/usr/bin/env bash
# Install 5G Core Network prerequisites for Arch/Parch Linux
# Installs SCTP support and ensures TUN/TAP devices are available

set -e

echo "=== 5G Core Network Prerequisites Installation ==="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "⚠️  This script needs root privileges."
    echo "   Running with sudo..."
    exec sudo "$0" "$@"
fi

echo "[1/4] Installing SCTP tools..."
if pacman -Q lksctp-tools &>/dev/null; then
    echo "✅ lksctp-tools already installed"
else
    pacman -S --noconfirm lksctp-tools
    echo "✅ lksctp-tools installed"
fi

echo ""
echo "[2/4] Loading SCTP kernel module..."
if lsmod | grep -q sctp; then
    echo "✅ SCTP module already loaded"
else
    modprobe sctp
    echo "✅ SCTP module loaded"
fi

# Verify SCTP is working
if lsmod | grep -q sctp; then
    echo "✅ SCTP module verified"
else
    echo "❌ ERROR: Failed to load SCTP module"
    exit 1
fi

echo ""
echo "[3/4] Ensuring /dev/net/tun is available..."
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
echo "[4/4] Making kernel modules persistent across reboots..."
mkdir -p /etc/modules-load.d/
if ! grep -q "^sctp$" /etc/modules-load.d/5g-core.conf 2>/dev/null; then
    echo "sctp" > /etc/modules-load.d/5g-core.conf
    echo "✅ SCTP module will load on boot"
else
    echo "✅ SCTP module already configured for boot"
fi

if ! grep -q "^tun$" /etc/modules-load.d/5g-core.conf 2>/dev/null; then
    echo "tun" >> /etc/modules-load.d/5g-core.conf
    echo "✅ TUN module will load on boot"
else
    echo "✅ TUN module already configured for boot"
fi

echo ""
echo "═══════════════════════════════════════════════"
echo "  ✅ All prerequisites installed!"
echo "═══════════════════════════════════════════════"
echo ""
echo "Loaded kernel modules:"
lsmod | grep -E "sctp|tun" || echo "  (modules integrated in kernel)"
echo ""
echo "You can now deploy the 5G core:"
echo "  ./scripts/deploy_5g_core.sh"
echo ""
