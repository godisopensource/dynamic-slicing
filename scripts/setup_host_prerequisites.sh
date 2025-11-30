#!/bin/bash
# Install 5G Core Network prerequisites for Arch/Parch Linux and Ubuntu/Debian
# Installs SCTP support and ensures TUN/TAP devices are available

set -e

echo "=== 5G Core Network Prerequisites Setup ==="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "⚠️  This script needs root privileges."
    echo "   Running with sudo..."
    exec sudo "$0" "$@"
fi

echo "[1/4] Installing SCTP tools..."
if command -v pacman &> /dev/null; then
    # Arch / Parch
    if pacman -Q lksctp-tools &>/dev/null; then
        echo "✅ lksctp-tools already installed"
    else
        pacman -S --noconfirm lksctp-tools
        echo "✅ lksctp-tools installed"
    fi
elif command -v apt-get &> /dev/null; then
    # Ubuntu / Debian
    apt-get update
    apt-get install -y libsctp-dev lksctp-tools
    # Try to install linux-modules-extra for current kernel if available (often needed for sctp module)
    apt-get install -y linux-modules-extra-$(uname -r) || echo "   (linux-modules-extra not found, skipping)"
    echo "✅ SCTP tools installed"
else
    echo "⚠️  Unsupported package manager. Please install lksctp-tools manually."
fi

echo ""
echo "[2/4] Loading SCTP kernel module..."
if lsmod | grep -q sctp; then
    echo "✅ SCTP module already loaded"
else
    if modprobe sctp; then
        echo "✅ SCTP module loaded"
    else
        echo "❌ ERROR: Failed to load SCTP module. Please check your kernel modules."
        exit 1
    fi
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

# SCTP
if ! grep -q "^sctp$" /etc/modules-load.d/5g-core.conf 2>/dev/null; then
    echo "sctp" >> /etc/modules-load.d/5g-core.conf
    echo "✅ SCTP module configured for boot"
else
    echo "✅ SCTP module already configured for boot"
fi

# TUN
if ! grep -q "^tun$" /etc/modules-load.d/5g-core.conf 2>/dev/null; then
    echo "tun" >> /etc/modules-load.d/5g-core.conf
    echo "✅ TUN module configured for boot"
else
    echo "✅ TUN module already configured for boot"
fi

# Also try /etc/modules for older systems/Debian
if [ -f /etc/modules ]; then
    if ! grep -q "^sctp$" /etc/modules; then
        echo "sctp" >> /etc/modules
    fi
    if ! grep -q "^tun$" /etc/modules; then
        echo "tun" >> /etc/modules
    fi
fi

echo ""
echo "═══════════════════════════════════════════════"
echo "  ✅ All prerequisites installed!"
echo "═══════════════════════════════════════════════"
echo ""
echo "Loaded kernel modules:"
lsmod | grep -E "sctp|tun" || echo "  (modules integrated in kernel)"
echo ""
