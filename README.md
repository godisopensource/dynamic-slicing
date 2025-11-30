# NexSlice — Contrôleur de Slicing Dynamique 5G

**Auteurs :** Lardet Paul et Jarlan Benoit  
**Date :** 30 novembre 2025

---

## 1. État de l'Art

### 1.1. Contexte et Objectifs
L'évolution vers la 5G Standalone (SA) introduit la séparation du plan de contrôle et du plan utilisateur (**CUPS** - *Control and User Plane Separation*), définie dans la spécification 3GPP TS 23.501. Cette architecture permet de placer les fonctions de traitement de données (UPF) au plus près de l'utilisateur (Edge Computing) et de les instancier dynamiquement.

L'objectif de ce projet est de dépasser le déploiement statique traditionnel pour atteindre une **instanciation automatisée de l'UPF déclenchée par la connexion d'un UE**.

### 1.2. Analyse des Standards et Technologies
*   **Identification du Slice (S-NSSAI) :** Le standard utilise le couple SST (*Slice Service Type*) et SD (*Slice Differentiator*) pour router le trafic. C'est le déclencheur (*trigger*) de notre logique d'orchestration.
*   **Orchestration Kubernetes :** L'état de l'art industriel privilégie le pattern **Opérateur Kubernetes** (boucle de réconciliation) pour gérer le cycle de vie des applications.
*   **Solutions existantes :**
    *   *Open5GS-operator* : Approche opérateur complète mais complexe.
    *   *KEDA* : Autoscaling basé sur des événements, pertinent mais nécessite des métriques custom.
    *   *Approche Script/API* : Plus flexible pour le prototypage rapide d'une logique métier spécifique ("1 UE = 1 UPF").

### 1.3. Positionnement du Projet
NexSlice se positionne comme un **Orchestrateur Léger** (Lightweight Orchestrator). Plutôt que de développer un Opérateur Kubernetes complexe (CRDs, Controller Runtime) ou d'utiliser des scripts Bash fragiles, nous avons opté pour un **Contrôleur REST (Flask)** qui interagit directement avec l'API Kubernetes. Cela permet une logique impérative claire pour la démonstration tout en restant Cloud-Native.

---

## 2. Méthode Choisie et Justification

### 2.1. Architecture "1 UE = 1 UPF"
Nous avons choisi une granularité fine : **chaque équipement utilisateur (UE) dispose de son propre UPF dédié**.

*   **Justification :** Cette approche garantit une isolation totale des ressources (CPU/RAM/Bande passante) pour chaque utilisateur, simulant un cas d'usage critique (ex: chirurgie à distance, V2X) où la performance ne doit pas être impactée par les voisins.

### 2.2. Le Contrôleur Centralisé (Flask)
Le cœur du système est une application Python/Flask qui agit comme un chef d'orchestre.

*   **Pourquoi Python/Flask ?**
    *   Rapidité de développement et richesse des librairies (client Kubernetes officiel).
    *   Exposition facile d'une API REST pour l'intégration avec des systèmes tiers (OSS/BSS).
    *   Capacité à générer dynamiquement des configurations (fichiers YAML pour UERANSIM et OAI-UPF) avant de les appliquer.

### 2.3. Workflow d'Instanciation Dynamique
1.  **Réception de la demande :** L'API reçoit une requête de création d'UE.
2.  **Génération de Configuration :** Le contrôleur génère une configuration unique (IMSI, Clés, IP) pour l'UE.
3.  **Déploiement UPF :** Le contrôleur ordonne à Kubernetes de déployer un nouveau Pod UPF, étiqueté spécifiquement pour cet UE (`app=upf`, `ue-id=X`).
4.  **Déploiement UE :** Une fois l'UPF prêt, l'UE est déployé et configuré pour se connecter au gNB.
5.  **Monitoring :** Le contrôleur met à jour les métriques Prometheus pour refléter la nouvelle charge.

---

## 3. Résultats Illustrés

### 3.1. Démonstration Vidéo
Une vidéo de démonstration complète du scénario (création UE, instanciation UPF, trafic, suppression) est disponible :

[🎥 Voir la vidéo de démonstration](DYNAMIC_SLICING_DEMO_VIDEO.mp4)

### 3.1. Instanciation Dynamique Réussie
Le système parvient à instancier un couple UE/UPF complet en moins de **15 secondes** (temps de démarrage des conteneurs inclus).

![Interface Web NexSlice](docs/images/web_interface.png)

*   **Preuve :** La commande `kubectl get pods` montre l'apparition dynamique des paires :
    ```text
    NAME                            READY   STATUS    AGE
    ueransim-ue-1                   1/1     Running   12s
    upf-ue1-6d4b7d9f8-xk2qz         1/1     Running   10s
    ```

### 3.2. Isolation du Trafic (Traffic Steering)
Les tests de capture de trafic (via `tcpdump` sur l'UPF) confirment que les paquets ICMP générés par l'UE transitent bien par son UPF dédié et non par un UPF partagé.

![Preuve de Ping et Latence](docs/images/ping_test_proof.png)

*   **Validation :** Le script `scripts/demo_traffic_capture.sh` automatise cette vérification en corrélant l'IP de l'interface TUN de l'UE avec les paquets vus sur l'interface réseau de l'UPF.

### 3.3. Monitoring Temps Réel
L'intégration Prometheus/Grafana permet de visualiser :
*   Le nombre d'UEs actifs.
*   La consommation de ressources par Slice (CPU/RAM de chaque UPF).
*   Le débit montant/descendant au niveau du gNB.

![Dashboard Grafana](docs/images/grafana_dashboard.png)

*(Les dashboards JSON sont fournis dans le dossier `docs/`)*

---

## 4. Conclusion

Le projet NexSlice démontre la faisabilité d'un **slicing dynamique granulaire** dans un environnement 5G Standalone open-source. En couplant la flexibilité de l'API Kubernetes avec la logique métier d'un contrôleur Python, nous avons réussi à automatiser le cycle de vie complet des fonctions réseaux (UPF) en réponse à la demande utilisateur.

Cette architecture constitue une base solide pour des cas d'usage avancés comme le *Network Slicing as a Service* (NSaaS), où l'infrastructure s'adapte en temps réel aux besoins des clients verticaux.

---

## 5. Guide de Reproduction (Installation & Usage)

Cette section contient l'ensemble des scripts et instructions nécessaires pour reproduire l'intégration.

### 5.1. Prérequis

- **OS :** Linux (Arch ou Ubuntu recommandé) ou macOS (pour le contrôleur uniquement).
- **Kubernetes :** Cluster fonctionnel (k3s, k8s, kind...).
- **Outils :** `kubectl`, `helm`, `python3`, `pip`, `git`.

### 5.2. Installation Automatisée

#### Étape 1 : Préparation de l'hôte (Linux)
Le cœur 5G nécessite des modules noyau spécifiques (SCTP, TUN). Lancez ce script **une seule fois** :

```bash
sudo ./scripts/setup_host_prerequisites.sh
```

#### Étape 2 : Déploiement Complet (Script "Tout-en-un")
Le script `start.sh` déploie le cœur 5G (si absent), installe les dépendances Python, et lance le contrôleur + monitoring.

```bash
chmod +x start.sh
./start.sh
```

> **Note :** Le déploiement initial du cœur 5G (OAI) peut prendre 5 à 10 minutes le temps que les images Docker soient téléchargées.

### 5.3. Utilisation et Démos

Une fois le contrôleur lancé (accessible sur `http://localhost:5000`), vous pouvez utiliser les scripts de démonstration fournis dans `scripts/`.

#### Scénario 1 : Cycle de Vie Complet
Crée un UE, vérifie que son UPF dédié est créé, puis nettoie tout.

```bash
./scripts/demo_lifecycle.sh <ue_id>
# Exemple : ./scripts/demo_lifecycle.sh 1
```

#### Scénario 2 : Preuve de Trafic
Vérifie que le trafic de l'UE passe réellement par l'UPF dédié (Ping + Capture de paquets).

```bash
./scripts/demo_traffic_capture.sh
```

#### Scénario 3 : Métriques Radio
Vérifie que les métriques du gNB remontent bien dans Prometheus.

```bash
./scripts/test_gnb_metrics.sh
```

### 5.4. Interface Web et API

*   **Web UI :** http://localhost:5000 (Gestion visuelle des UEs)
*   **Prometheus :** http://localhost:9090
*   **Grafana :** http://localhost:3000 (Login: `admin`/`admin`)

**Endpoints API Principaux :**
*   `POST /add_pod` : Créer un UE + UPF.
*   `POST /remove_pod/<id>` : Supprimer un UE + UPF.
*   `GET /metrics` : Métriques pour Prometheus.

---

## 6. Architecture Technique

```
┌──────────────────────────────────────────────────────────┐
│                   Flask Controller                       │
│  (src/main.py - port 5000)                               │
│  • API REST pour créer/supprimer UE/UPF                 │
│  • Logique d'orchestration "1 UE = 1 UPF"                │
└────────────────┬─────────────────────────────────────────┘
                 │ (Kubernetes API)
                 ▼
┌──────────────────────────────────────────────────────────┐
│        Kubernetes Cluster (namespace: nexslice)          │
│                                                          │
│  ┌──────────────────┐       ┌──────────────────┐         │
│  │  5G Core (OAI)   │ <──── │  UERANSIM gNB    │         │
│  └──────────────────┘       └─────────┬────────┘         │
│           ▲                           │                  │
│           │ (N4 Interface)            │ (Radio Link)     │
│           ▼                           ▼                  │
│  ┌─────────────────┐        ┌──────────────────┐         │
│  │  UPF Pod (Dédié)│ <────> │  UE Pod          │         │
│  └─────────────────┘        └──────────────────┘         │
└──────────────────────────────────────────────────────────┘
```

## 7. Crédits

Projet basé sur :
- [AIDY-F2N/NexSlice](https://github.com/AIDY-F2N/NexSlice)
- [OpenAirInterface](https://www.openairinterface.org/)
- [UERANSIM](https://github.com/aligungr/UERANSIM)
