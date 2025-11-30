#!/usr/bin/env fish

echo "═══════════════════════════════════════════════════════════════════════"
echo "  Démonstration: Trafic UE → UPF dédié"
echo "═══════════════════════════════════════════════════════════════════════"
echo ""

# Fonction pour extraire l'IP d'un UE
function get_ue_ip
    set ue_name $argv[1]
    kubectl logs -n nexslice $ue_name 2>/dev/null | grep "TUN interface" | sed -n 's/.*\[\([0-9.]*\)\].*/\1/p'
end

echo "🔍 Étape 1: Identification des UEs et leurs IPs"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
set ue_pods (kubectl get pods -n nexslice -o name | grep ueransim-ue | sed 's/pod\///')

for ue in $ue_pods
    set ue_ip (get_ue_ip $ue)
    if test -n "$ue_ip"
        echo "  ✓ $ue → IP: $ue_ip"
    else
        echo "  ⚠ $ue → Pas encore d'IP (attendre la connexion)"
    end
end
echo ""

echo "🔍 Étape 2: Correspondance UE ↔ UPF"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
for ue in $ue_pods
    set ue_num (echo $ue | sed 's/ueransim-ue//')
    set upf_name "upf-ue$ue_num"
    
    if kubectl get pod -n nexslice $upf_name &>/dev/null
        echo "  ✓ $ue ← → $upf_name"
    else
        echo "  ✗ $ue ← → $upf_name (UPF manquant!)"
    end
end
echo ""

echo "🔍 Étape 3: Vérification dans les logs SMF"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Sessions PDU établies récemment:"
kubectl logs -n nexslice -l app.kubernetes.io/name=oai-smf --tail=500 2>/dev/null | \
    grep -E "SUPI.*20895|PAA IPv4" | tail -8
echo ""

echo "🔍 Étape 4: Test pratique - Capture de trafic"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

set test_ue $ue_pods[1]
set ue_num (echo $test_ue | sed 's/ueransim-ue//')
set test_upf "upf-ue$ue_num"
set ue_ip (get_ue_ip $test_ue)

if test -z "$ue_ip"
    echo "  ⚠ $test_ue n'a pas encore d'IP. Attendre la connexion PDU."
    exit 1
end

echo "  Test: $test_ue (IP: $ue_ip) → $test_upf"
echo ""
echo "  📤 Génération de 5 pings depuis l'UE vers 8.8.8.8..."
echo "  🎯 Capture simultanée sur l'UPF $test_upf..."
echo ""

# Lancer capture en arrière-plan
kubectl exec -n nexslice $test_upf -- timeout 15 tcpdump -i any -n "host $ue_ip or port 2152" -l 2>&1 &
set capture_pid $last_pid
sleep 2

# Générer trafic
kubectl exec -n nexslice $test_ue -- ping -c 5 -i 1 8.8.8.8 >/dev/null 2>&1

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
# Demo script pour créer un UE, vérifier l'UPF créé, puis supprimer le UE et vérifier la suppression de l'UPF.
# Prérequis: kubectl configuré (contexte vers le cluster), curl, et le serveur Flask démarré (par ex: python -m src.main)

if not type -q jq
    echo "jq est requis pour parser la réponse JSON de l'API (/api/ue-count). Installe-le puis relance le script."
    exit 1
end

if test (count $argv) -lt 1
    echo "Usage: demo.sh <ue_id>"
    exit 1
end

set UE_ID $argv[1]
set BASE_URL http://localhost:5000

echo "Création de l'UE $UE_ID via l'API..."
curl -s -X POST "$BASE_URL/add_pod" -o /dev/null

# Le endpoint add_pod crée l'UE avec un nouvel index ; le script d'API ne permet pas d'indiquer l'ID explicitement.
# Pour une démo contrôlée, on récupère le dernier UE créé via /api/ue-count
set COUNT_RESPONSE (curl -sf "$BASE_URL/api/ue-count")
if test $status -ne 0 -o -z "$COUNT_RESPONSE"
    echo "Impossible de récupérer le compteur d'UE sur $BASE_URL/api/ue-count. L'application Flask tourne-t-elle bien ?"
    exit 1
end

set COUNT (printf '%s' "$COUNT_RESPONSE" | jq -r '.count // 0')
if test -z "$COUNT"; or test "$COUNT" = "null"
    echo "Réponse /api/ue-count invalide: $COUNT_RESPONSE"
    exit 1
end

if not string match -rq '^[0-9]+$' -- $COUNT
    echo "Le champ 'count' n'est pas numérique: $COUNT_RESPONSE"
    exit 1
end

if test $COUNT -eq 0
    echo "Aucun UE trouvé après la création. Vérifiez le service Flask."
    exit 1
end

echo "Dernier UE créé: $COUNT (on vérifie l'UPF upf-ue$COUNT)"

echo "Attente 3s pour que les ressources K8s soient créées..."
sleep 3

# Vérifier si kubectl peut parler à un cluster. Si non, sauter les vérifications K8s.
if kubectl version --client >/dev/null 2>&1; and kubectl cluster-info >/dev/null 2>&1
    echo "Vérification K8s: cluster accessible, affichage des ressources..."
    kubectl get deployment upf-ue$COUNT -n nexslice --ignore-not-found
    kubectl get svc upf-ue$COUNT -n nexslice --ignore-not-found
else
    echo "Aucun cluster Kubernetes accessible via kubectl : les vérifications K8s sont sautées."
end

read -P "Appuyez sur Entrée pour supprimer l'UE et l'UPF..." dummy

# Supprimer via l'endpoint remove_pod
curl -s -X POST "$BASE_URL/remove_pod/$COUNT" -o /dev/null

sleep 2

echo "Vérification après suppression:"
if kubectl version --client >/dev/null 2>&1; and kubectl cluster-info >/dev/null 2>&1
    kubectl get deployment upf-ue$COUNT -n nexslice --ignore-not-found
    kubectl get svc upf-ue$COUNT -n nexslice --ignore-not-found
else
    echo "Aucun cluster Kubernetes accessible via kubectl : les vérifications K8s sont sautées."
end

echo "Demo terminée."
