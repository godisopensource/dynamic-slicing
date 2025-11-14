## Dépôts GitHub pour le Network Slicing Dynamique 5G avec Kubernetes

Voici une sélection de dépôts GitHub et projets open-source qui implémentent le slicing dynamique de réseaux 5G avec création/suppression automatique d'UPF sur Kubernetes, correspondant à vos besoins pour NexSlice :

### 1. **Gradiant/open5gs-operator**

Ce projet fournit un **opérateur Kubernetes** pour automatiser le déploiement et la gestion du cycle de vie d'Open5GS.[1][2]

**Caractéristiques principales :**
- Gestion déclarative des déploiements Open5GS via des Custom Resource Definitions (CRDs)
- Configuration automatique des slices réseau
- Gestion du cycle de vie des composants (activation/désactivation, reconfiguration)
- Support multi-namespace pour l'isolation des ressources
- Détection et correction automatique des dérives de configuration

**Lien :** https://github.com/Gradiant/open5gs-operator

**Limitations :** L'opérateur ne crée/supprime pas automatiquement les UPF en fonction de la connexion/déconnexion des UEs, mais permet une gestion déclarative qui pourrait être étendue avec un contrôleur personnalisé.[1]

### 2. **Projet de Slicing Dynamique avec Prometheus/Alertmanager**

Un projet utilise **Prometheus, Alertmanager et des webhooks Python** pour automatiser la création/suppression d'instances SMF et UPF dans Open5GS.[3]

**Architecture et fonctionnement :**
- **Prometheus** surveille les métriques du core 5G (nombre d'UEs par slice)
- Lorsqu'un seuil est atteint (ex : 5 UEs par SMF/UPF), **Alertmanager** génère une alerte
- L'alerte est envoyée à un **webhook** qui déclenche un **script Python**
- Le script Python crée dynamiquement de nouveaux conteneurs Docker pour SMF et UPF avec les configurations appropriées
- Les nouveaux UEs sont automatiquement dirigés vers les nouvelles instances

**Résultats :** Ce système réduit de 47,5% les demandes de reconfiguration et permet un scaling sans interruption de service.[4][3]

**Limitation :** Utilise Docker Compose plutôt que Kubernetes natif, nécessitant une adaptation manuelle du scaling.[3]

### 3. **niloysh/open5gs-k8s et 5G-Monarch**

Ce dépôt déploie **Open5GS sur Kubernetes avec support du network slicing** et inclut une architecture de monitoring (Monarch).[5][6]

**Caractéristiques :**
- Déploiement de slices avec SMF et UPF dédiés par slice
- Architecture cloud-native avec monitoring per-slice
- Collecte de métriques et calcul de KPIs spécifiques à chaque slice
- Gestion de plusieurs slices avec isolation des ressources

**Lien :** https://github.com/niloysh/open5gs-k8s

**Note :** Ce projet se concentre sur le monitoring plutôt que sur l'auto-scaling dynamique basé sur les connexions UE.[6]

### 4. **HEXAeBPF - Opérateur Kubernetes pour 5G Core**

**HEXAeBPF** est un opérateur Kubernetes qui simplifie le déploiement de réseaux 5G en intégrant différents plans de contrôle et d'utilisateur.[7][8][9]

**Fonctionnalités :**
- Déploiement one-click via Custom Resource Definitions (CRDs)
- Gestion automatique du cycle de vie des Network Functions
- Support de l'auto-scaling et self-healing via Kubernetes
- Interopérabilité entre différentes implémentations (Free5GC, Open5GS, OAI, SD-Core)
- Intégration d'UPF basés sur eBPF pour meilleures performances

**Liens :**
- https://github.com/coranlabs/HEXAeBPF
- Documentation : https://docs.ngkore.org/

### 5. **towards5gs-helm**

Projet Helm pour déployer un système 5G complet (Free5GC + UERANSIM) sur Kubernetes en un clic.[10][11]

**Caractéristiques :**
- Déploiement simplifié via Helm charts
- Support du RAN et du Core 5G
- Architecture cloud-native
- Base pour l'ajout de fonctionnalités de slicing dynamique

**Lien :** https://github.com/Orange-OpenSource/towards5gs-helm

**Limitation :** Pas de support natif pour le slicing dynamique.[12]

### 6. **fhgrings/5g-core-network-slicing (ODT-5gc)**

Projet d'infrastructure avec **Terraform, Ansible et Kubernetes** pour le déploiement de Free5GC avec monitoring.[13][4]

**Architecture :**
- Cluster Kubernetes (K3s/K8s) sur AWS ou Proxmox
- Monitoring avec Prometheus et Grafana
- Focus sur l'observabilité et le slicing réseau
- Utilisation de CNI multiples (Flannel + Multus pour l'UPF)

**Lien :** https://github.com/fhgrings/5g-core-network-slicing

**Note :** Le projet se concentre sur l'infrastructure et le monitoring plutôt que sur l'auto-scaling dynamique.[14][4]

### 7. **Solutions d'Auto-Scaling avec KEDA**

Le projet **Aether SD-Core** utilise **KEDA (Kubernetes Event-driven Autoscaling)** pour scaler automatiquement les Network Functions 5G.[15]

**Fonctionnement :**
- KEDA surveille des métriques personnalisées (ex : messages N4 vers le SMF)
- Scale automatiquement les pods en fonction des seuils définis
- Support du HPA (Horizontal Pod Autoscaler) de Kubernetes
- Scale-up pour gérer l'augmentation du trafic, scale-down pour économiser les ressources

**Exemple de configuration :**
```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: smf-scale
spec:
  scaleTargetRef:
    name: smf
  minReplicaCount: 1
  maxReplicaCount: 5
  triggers:
    - type: prometheus
      metadata:
        query: sum(n4_messages_total{job="smf"})
        threshold: "50"
```

**Documentation :** https://docs.sd-core.aetherproject.org/

### Recommandations pour votre projet NexSlice

Pour implémenter votre objectif de slicing dynamique, je vous recommande :

1. **Architecture hybride :**
   - Utiliser **open5gs-operator** comme base pour la gestion déclarative[1]
   - Ajouter un **contrôleur custom Kubernetes** qui surveille les événements de connexion/déconnexion des UEs
   - Intégrer **KEDA** pour l'auto-scaling basé sur des métriques[15]

2. **Pipeline d'automatisation :**
   - **Prometheus** pour collecter les métriques des UEs connectés[16][17]
   - **Operator pattern** pour réagir aux événements de connexion UE
   - Création automatique de ressources Kubernetes (Deployment, Service) pour les nouveaux UPFs
   - Utilisation de **StatefulSets** pour les UPFs avec identité stable

3. **Références techniques utiles :**
   - L'approche avec Prometheus/Alertmanager/Webhook peut être adaptée à Kubernetes[3]
   - Les métriques exposées par Open5GS sont compatibles avec Prometheus[16]
   - Les opérateurs Kubernetes permettent d'automatiser les opérations complexes[7][1]

4. **Exemple de workflow :**
   ```
   UE connexion → AMF détecte → Métriques Prometheus → 
   Contrôleur K8s → Création UPF Pod → Configuration SMF → 
   PDU Session établie
   
   UE déconnexion → Détection idle → Graceful shutdown → 
   Suppression UPF Pod → Libération ressources
   ```
