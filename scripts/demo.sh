#!/usr/bin/env fish
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
