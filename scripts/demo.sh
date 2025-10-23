#!/usr/bin/env fish
# Demo script pour créer un UE, vérifier l'UPF créé, puis supprimer le UE et vérifier la suppression de l'UPF.
# Prérequis: kubectl configuré (contexte vers le cluster), curl, et le serveur Flask démarré (par ex: python -m src.main)

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
set COUNT (curl -s "$BASE_URL/api/ue-count" | python -c "import sys, json; print(json.load(sys.stdin)['count'])")
if test $COUNT -eq 0
    echo "Aucun UE trouvé après la création. Vérifiez le service Flask."
    exit 1
end

echo "Dernier UE créé: $COUNT (on vérifie l'UPF upf-ue$COUNT)"

echo "Attente 3s pour que les ressources K8s soient créées..."
sleep 3

kubectl get deployment upf-ue$COUNT -n nexslice --ignore-not-found
kubectl get svc upf-ue$COUNT -n nexslice --ignore-not-found

read -P "Appuyez sur Entrée pour supprimer l'UE et l'UPF..." dummy

# Supprimer via l'endpoint remove_pod
curl -s -X POST "$BASE_URL/remove_pod/$COUNT" -o /dev/null

sleep 2

echo "Vérification après suppression:"
kubectl get deployment upf-ue$COUNT -n nexslice --ignore-not-found
kubectl get svc upf-ue$COUNT -n nexslice --ignore-not-found

echo "Demo terminée."
