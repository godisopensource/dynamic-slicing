#!/usr/bin/env fish

echo "=== Test des métriques gNB dans Prometheus ==="
echo ""

echo "1. Vérification que le pod gNB est accessible :"
set GNB_IP (kubectl get pod ueransim-gnb -n nexslice -o jsonpath='{.status.podIP}')
echo "   IP du gNB: $GNB_IP"
echo ""

echo "2. Test direct de l'endpoint metrics du gNB :"
kubectl exec -n nexslice ueransim-gnb -c network-exporter -- sh -c "curl -s http://localhost:8000/metrics | grep gnb_network | head -4"
echo ""

echo "3. Vérification dans Prometheus :"
curl -s "http://localhost:9090/api/v1/query?query=gnb_network_receive_bytes_total" | python3 -c "
import json, sys
data = json.load(sys.stdin)
if data['data']['result']:
    result = data['data']['result'][0]
    value = result['value'][1]
    print(f\"   ✓ Métrique trouvée: {value} bytes reçus\")
else:
    print('   ✗ Aucune métrique trouvée')
"
echo ""

echo "4. Test de la requête rate (pour Grafana) :"
curl -s 'http://localhost:9090/api/v1/query?query=rate(gnb_network_receive_bytes_total[2m])' | python3 -c "
import json, sys
data = json.load(sys.stdin)
if data['data']['result']:
    result = data['data']['result'][0]
    value = result['value'][1]
    print(f\"   ✓ Rate calculé: {value} bytes/sec\")
else:
    print('   ! Pas assez de données pour calculer rate (attendre 2+ minutes)')
"
echo ""

echo "=== Prêt pour Grafana ! ==="
echo "Importe maintenant le fichier: gnb-traffic-dashboard.json"
