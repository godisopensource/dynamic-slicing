# Monitoring avec Prometheus & Grafana

Ce projet expose désormais des métriques Prometheus via l'endpoint `GET /metrics` (port 5000 par défaut). Voici ce qui est fourni :

| métrique | description |
| --- | --- |
| `nexslice_active_ues` | Gauge qui reflète le nombre de fichiers de configuration UE disponibles (`./tmp/ue-confs/ue*.yaml`). Elle est mise à jour après chaque création ou suppression de UE. |
| `nexslice_upf_creations_total` | Counter représentant les créations d'UPF (Deployment + Service). |
| `nexslice_upf_deletions_total` | Counter représentant les suppressions d'UPF correspondantes. |

Ces métriques sont suffisantes pour construire un tableau de bord Grafana et déclencher des règles Prometheus ou KEDA si tu veux scaler/redémarrer des UPF en fonction charge UE.

## Exemple de configuration Prometheus

Ajoute ce job dans ton `prometheus.yml` pour scrapper l'app NexSlice :

```yaml
scrape_configs:
  - job_name: nexslice-controller
    metrics_path: /metrics
    static_configs:
      - targets:
          - "host.docker.internal:5000"  # ou 127.0.0.1:5000 si Prometheus tourne sur la même machine
```

Remplace `host.docker.internal` par l'adresse ou le service Kubernetes exposé si tu déploies `nexslice-controller` dans un cluster.

## Exemple de dashboard Grafana

1. Crée un nouveau dashboard dans Grafana et ajoute trois panneaux :
   - **Gauge** `UE actifs` (`nexslice_active_ues`). Affiche le nombre total d'UEs.
   - **Stat** `UPF créés` (`increase(nexslice_upf_creations_total[5m])`). Mesure le taux de création sur 5 minutes.
   - **Stat** `UPF supprimés` (`increase(nexslice_upf_deletions_total[5m])`). Mesure la suppression.
2. Tu peux ajouter un panneau `Graph` pour visualiser l'évolution de `nexslice_active_ues` sur le temps :

```promql
graph: nexslice_active_ues
```

3. Pour visualiser les opérations UPF en temps réel :
   - Panneau `Bar Gauge` avec le ratio `nexslice_upf_creations_total` vs `nexslice_upf_deletions_total` en utilisant la fonction `rate()` sur 1 minute.

Grafana permet aussi d'utiliser les alertes pour avertir si `nexslice_active_ues` dépasse un seuil et déclencher une automatisation (KEDA / webhook) vers `/api/ue-connect` ou `/api/ue-disconnect`.

## Options avancées

- **Alertmanager → Webhook** : utilise la configuration Alertmanager pour appeler `/api/ue-connect` quand un seuil est atteint (par exemple `nexslice_active_ues > 10`). 
- **KEDA** : en complément, un `ScaledObject` KEDA peut surveiller la métrique `nexslice_active_ues` ou `rate(nexslice_upf_creations_total[1m])` pour scaler `upf-ue*`. Ce contrôleur étant déjà responsable de la création/suppression, KEDA peut déclencher des objets Kubernetes séparés (ex: un Deployment `upf-autoscaler`).

Tu peux référencer ce fichier dans la doc principale (`README.md`) pour guider la configuration de la stack de monitoring.