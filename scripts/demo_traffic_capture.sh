#!/bin/bash

echo "═══════════════════════════════════════════════════════════════════════"
echo "  Démonstration: Trafic UE → UPF dédié"
echo "═══════════════════════════════════════════════════════════════════════"
echo ""

# Function to extract UE IP
get_ue_ip() {
    local ue_name=$1
    kubectl logs -n nexslice "$ue_name" 2>/dev/null | grep "TUN interface" | sed -n 's/.*\[\([0-9.]*\)\].*/\1/p'
}

echo "🔍 Étape 1: Identification des UEs et leurs IPs"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
ue_pods=$(kubectl get pods -n nexslice -o name | grep ueransim-ue | sed 's/pod\///')

for ue in $ue_pods; do
    ue_ip=$(get_ue_ip "$ue")
    if [ -n "$ue_ip" ]; then
        echo "  ✓ $ue → IP: $ue_ip"
    else
        echo "  ⚠ $ue → Pas encore d'IP (attendre la connexion)"
    fi
done
echo ""

echo "🔍 Étape 2: Correspondance UE ↔ UPF"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
for ue in $ue_pods; do
    ue_num=$(echo "$ue" | sed 's/ueransim-ue//')
    upf_name="upf-ue$ue_num"
    
    if kubectl get pod -n nexslice "$upf_name" &>/dev/null; then
        echo "  ✓ $ue ← → $upf_name"
    else
        echo "  ✗ $ue ← → $upf_name (UPF manquant!)"
    fi
done
echo ""

echo "🔍 Étape 3: Vérification dans les logs SMF"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Sessions PDU établies récemment:"
kubectl logs -n nexslice -l app.kubernetes.io/name=oai-smf --tail=500 2>/dev/null | \
    grep -E "SUPI.*20895|PAA IPv4" | tail -8
echo ""

echo "🔍 Étape 4: Test pratique - Capture de trafic"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Get the first UE
test_ue=$(echo "$ue_pods" | head -n 1)
if [ -z "$test_ue" ]; then
    echo "  ⚠ Aucun UE trouvé."
    exit 1
fi

ue_num=$(echo "$test_ue" | sed 's/ueransim-ue//')
test_upf="upf-ue$ue_num"
ue_ip=$(get_ue_ip "$test_ue")

if [ -z "$ue_ip" ]; then
    echo "  ⚠ $test_ue n'a pas encore d'IP. Attendre la connexion PDU."
    exit 1
fi

echo "  Test: $test_ue (IP: $ue_ip) → $test_upf"
echo ""
echo "  📤 Génération de 5 pings depuis l'UE vers 8.8.8.8..."
echo "  🎯 Capture simultanée sur l'UPF $test_upf..."
echo ""

# Start capture in background
kubectl exec -n nexslice "$test_upf" -- timeout 15 tcpdump -i any -n "host $ue_ip or port 2152" -l 2>&1 &
capture_pid=$!
sleep 2

# Generate traffic
kubectl exec -n nexslice "$test_ue" -- ping -c 5 -i 1 8.8.8.8 >/dev/null 2>&1

echo ""
echo "  Résultat de la capture:"
wait $capture_pid

echo ""
echo "═══════════════════════════════════════════════════════════════════════"
echo "  ✅ Si vous voyez des paquets avec l'IP $ue_ip dans la capture,"
echo "     cela prouve que le trafic de $test_ue passe par $test_upf !"
echo "═══════════════════════════════════════════════════════════════════════"
echo ""
echo "Commandes supplémentaires utiles:"
echo ""
echo "  # Voir compteurs réseau de l'UPF:"
echo "  kubectl exec -n nexslice $test_upf -- ip -s link show eth0"
echo ""
echo "  # Logs UPF (sessions PFCP):"
echo "  kubectl logs -n nexslice $test_upf | grep -i session"
echo ""
