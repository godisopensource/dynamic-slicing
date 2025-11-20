# NexSlice — Contrôleur de Slicing Dynamique 5G

Un contrôleur de slicing dynamique pour réseau 5G avec monitoring Prometheus/Grafana.  
**Chaque UE se voit attribuer un UPF dédié**, avec métriques exportées en temps réel.

---

## 📋 Prérequis

- **Kubernetes cluster** (k3s, k8s, kind, minikube...) avec `kubectl` configuré
- **Helm 3** installé (`helm version`)
- **Python 3.9+** et `pip`
- **Git** pour cloner les dépendances
- **(Optionnel)** Prometheus et Grafana pour le monitoring

---

## 🚀 Déploiement rapide

### 1. Déployer le cœur de réseau 5G (OAI)

⚠️ **Le projet nécessite un cœur de réseau 5G** (AMF, SMF, NRF, UDM, UDR, AUSF, NSSF, UPF, MySQL) pour que les UE et UPF puissent fonctionner.

Exécutez le script de déploiement automatique :

```bash
cd dynamic-slicing
chmod +x scripts/deploy_5g_core.sh
./scripts/deploy_5g_core.sh
```

Ce script va :
- Cloner le repo [AIDY-F2N/NexSlice](https://github.com/AIDY-F2N/NexSlice) dans `/tmp/NexSlice`
- Déployer via Helm le chart `oai-5g-advance` dans le namespace `nexslice`

✅ **Vérifiez que tous les pods du core sont en `Running`** :

```bash
kubectl get pods -n nexslice
```

Attendez que les pods `oai-amf`, `oai-smf`, `oai-nrf`, `mysql`, etc. soient tous `Running` (peut prendre 2-5 minutes).

---

### 2. Installer les dépendances Python

```bash
python -m venv .venv
source .venv/bin/activate  # ou .venv/bin/activate.fish pour fish shell
pip install -r requirements.txt
```

---

### 3. Lancer le contrôleur Flask

**Mode cluster (avec Kubernetes réel)** :

```bash
export DEMO_MODE=0
./.venv/bin/python -m src.main
```

**Mode démo (sans cluster, pour tests locaux)** :

```bash
export DEMO_MODE=1
./.venv/bin/python -m src.main
```

L'application démarre sur **http://localhost:5000**.

---

### 4. (Optionnel) Lancer Prometheus & Grafana

**Démarrer Prometheus** :

```bash
prometheus --config.file=prometheus.yml > /tmp/prometheus.log 2>&1 &
```

Accès : http://localhost:9090

**Démarrer Grafana** :

```bash
grafana-server --homepath /usr/share/grafana > /tmp/grafana.log 2>&1 &
```

Accès : http://localhost:3000 (login par défaut : `admin`/`admin`)

Dans Grafana :
1. Ajouter une source de données Prometheus → `http://localhost:9090`
2. Créer un dashboard pour visualiser :
   - `nexslice_active_ues` (nombre d'UE actifs)
   - `nexslice_upfs_total` (nombre total d'UPF déployés)

Un dashboard JSON prêt à l'emploi est disponible dans `prometheus-dashboard.json`.

---

## 🎯 Utilisation

### Interface Web

Accédez à **http://localhost:5000** pour :

- ➕ **Ajouter un UE** → Crée un pod UE + un UPF dédié dans Kubernetes
- 🔄 **Générer 100 UE** → Simulation de charge (crée 100 UE + 100 UPF)
- 🗑️ **Supprimer 100 UE** → Cleanup massif des ressources
- 📊 **Voir la liste des UE actifs** (auto-refresh toutes les 3 secondes)

### API Endpoints

| Endpoint | Méthode | Description |
|---|---|---|
| `/` | GET | Interface web principale |
| `/add_pod` | POST | Créer un UE + UPF dédié |
| `/create_pods` | POST | Générer 100 UE d'un coup |
| `/delete_pods` | POST | Supprimer les 100 UE + UPF |
| `/remove_pod/<ue_id>` | POST | Supprimer un UE spécifique |
| `/api/ue-count` | GET | Nombre de UE actifs (JSON) |
| `/api/ue-list` | GET | Liste JSON des UE |
| `/api/ue-connect` | POST | Simuler connexion UE |
| `/api/ue-disconnect` | POST | Simuler déconnexion UE |
| `/metrics` | GET | Métriques Prometheus |

**Exemple d'utilisation de l'API** :

```bash
# Créer un UE
curl -X POST http://localhost:5000/add_pod

# Lister les UE
curl http://localhost:5000/api/ue-list

# Supprimer l'UE numéro 5
curl -X POST http://localhost:5000/remove_pod/5

# Voir les métriques Prometheus
curl http://localhost:5000/metrics
```

### Métriques Prometheus

Deux métriques principales sont exposées :

- **`nexslice_active_ues`** : Nombre de UE configurés (compte basé sur les fichiers de config locaux)
- **`nexslice_upfs_total`** : Nombre total d'UPF déployés dans le cluster Kubernetes (ou approximation en DEMO_MODE)

Endpoint de scrape : `http://localhost:5000/metrics`

Configuration Prometheus : voir `prometheus.yml` (scrape toutes les 15 secondes).

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────────┐
│                   Flask Controller                       │
│  (src/main.py - port 5000)                               │
│  • API REST pour créer/supprimer UE/UPF                 │
│  • Exposition métriques Prometheus (/metrics)            │
│  • Interface web (HTML/JS)                               │
└────────────────┬─────────────────────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────────────────┐
│        Kubernetes Cluster (namespace: nexslice)          │
│                                                          │
│  ┌────────────────────────────────────────┐             │
│  │         5G Core Network (OAI)          │             │
│  │  • AMF (Access and Mobility Mgmt)      │             │
│  │  • SMF (Session Management Function)   │             │
│  │  • NRF (NF Repository Function)        │             │
│  │  • UDM, UDR, AUSF, NSSF                │             │
│  │  • MySQL (subscriber database)         │             │
│  └────────────────────────────────────────┘             │
│                                                          │
│  ┌─────────────────┐  ┌──────────────────┐             │
│  │  UERANSIM gNB   │  │  UE Pods         │             │
│  │  (simulateur)   │  │  (UERANSIM)      │             │
│  └─────────────────┘  │  • ueransim-ue1  │             │
│                        │  • ueransim-ue2  │             │
│  ┌─────────────────┐  │  • ...           │             │
│  │  UPF Pods       │  └──────────────────┘             │
│  │  (OAI UPF)      │                                    │
│  │  • upf-ue1      │  🔹 1 UPF dédié par UE            │
│  │  • upf-ue2      │                                    │
│  │  • ...          │                                    │
│  └─────────────────┘                                    │
└──────────────────────────────────────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────────────────┐
│       Prometheus + Grafana (monitoring)                  │
│  • Scrape /metrics toutes les 15s                        │
│  • Dashboards temps réel pour UE et UPF                  │
│  • Alerting sur seuils de charge                         │
└──────────────────────────────────────────────────────────┘
```

### Flux de création d'un UE

```
1. User → POST /add_pod
2. Flask génère config UERANSIM (IMSI, key, etc.)
3. Flask crée ConfigMap K8s avec la config
4. Flask crée Pod UERANSIM (monte le ConfigMap)
5. Flask crée Deployment + Service UPF dédié (labels app=upf, ue-id=X)
6. Flask rafraîchit les métriques Prometheus
7. UE pod démarre et se connecte au gNB/Core 5G
```

---

## 🐛 Dépannage

### ❌ Les pods UE ou UPF sont en CrashLoopBackOff

**1. Vérifier les logs** :
```bash
kubectl -n nexslice logs <pod-name>
kubectl -n nexslice logs <pod-name> --previous
```

**2. Vérifier les events Kubernetes** :
```bash
kubectl -n nexslice describe pod <pod-name>
kubectl -n nexslice get events --sort-by=.metadata.creationTimestamp | tail -n 50
```

**3. Causes fréquentes** :

| Symptôme | Cause probable | Solution |
|---|---|---|
| `ErrImagePull` / `ImagePullBackOff` | Image Docker introuvable | Vérifier le nom de l'image dans `src/main.py` |
| `exec: "/chemin": no such file or directory` | Binaire ou entrypoint incorrect | Corriger `command`/`args` ou laisser l'image utiliser son ENTRYPOINT |
| `OOMKilled` | Manque de mémoire | Augmenter `resources.limits.memory` |
| `Completed` puis redémarre | Le conteneur se termine avec succès mais k8s le relance | Vérifier `restartPolicy` (doit être `Always` pour services longs) |
| Logs : `Cannot connect to AMF/SMF` | Core 5G pas prêt | Attendre que `oai-amf`, `oai-smf`, etc. soient `Running` |

**4. Vérifier l'état du Core 5G** :
```bash
kubectl get pods -n nexslice -l app.kubernetes.io/name=oai-amf
kubectl get pods -n nexslice -l app.kubernetes.io/name=oai-smf
```

Si des pods du core sont en erreur, consultez leurs logs et redéployez le core si nécessaire.

---

### ❌ Le contrôleur Flask ne démarre pas

**Erreur : `ModuleNotFoundError`**

→ Installer les dépendances :
```bash
pip install -r requirements.txt
```

**Erreur : `Address already in use` sur le port 5000**

→ Un autre processus utilise le port. Trouver et arrêter le processus :
```bash
ss -ltnp | grep ':5000'
kill <PID>
```

**Erreur : `Unable to load kubeconfig`**

→ Si vous n'avez pas de cluster Kubernetes actif, lancez en mode DEMO :
```bash
export DEMO_MODE=1
python -m src.main
```

---

### ❌ Prometheus ne scrape pas les métriques

**1. Vérifier que Flask expose bien `/metrics`** :
```bash
curl http://localhost:5000/metrics
```

Vous devriez voir :
```
# HELP nexslice_active_ues Nombre d'UE configurés
# TYPE nexslice_active_ues gauge
nexslice_active_ues 0.0
# HELP nexslice_upfs_total Nombre total d'UPF déployés
# TYPE nexslice_upfs_total gauge
nexslice_upfs_total 0.0
```

**2. Vérifier la configuration Prometheus** :
```bash
cat prometheus.yml
```

Assurez-vous que `localhost:5000` est bien dans les `targets`.

**3. Vérifier les targets dans Prometheus UI** :

Accédez à http://localhost:9090/targets et vérifiez que `nexslice-controller` est `UP`.

---

### ❌ Grafana ne se connecte pas à Prometheus

**1. Vérifier que Prometheus est accessible** :
```bash
curl http://localhost:9090/api/v1/query?query=up
```

**2. Dans Grafana, configurer la datasource** :
- URL : `http://localhost:9090`
- Access : `Server (default)` ou `Browser` selon votre setup
- Cliquer sur "Save & Test"

---

## 📚 Documentation complémentaire

- **[docs/design.md](docs/design.md)** : Architecture détaillée et design du système
- **[docs/monitoring.md](docs/monitoring.md)** : Setup Prometheus/Grafana approfondi
- **[ETAT_ART.md](ETAT_ART.md)** : État de l'art du network slicing 5G

---

## 🧪 Tests

Lancer les tests d'intégration (en DEMO_MODE par défaut) :

```bash
pytest tests/test_dynamic_upf.py -v
```

Pour tester avec un vrai cluster :

```bash
export DEMO_MODE=0
pytest tests/test_dynamic_upf.py -v
```

---

## 🔧 Variables d'environnement

| Variable | Valeur par défaut | Description |
|---|---|---|
| `DEMO_MODE` | `0` | `1` = mode démo (pas de K8s), `0` = mode cluster réel |
| `UPF_IMAGE` | `oaisoftwarealliance/oai-upf:latest` | Image Docker pour les UPF |
| `UPF_REPLICAS` | `1` | Nombre de replicas par UPF Deployment |

**Exemple** :

```bash
export DEMO_MODE=0
export UPF_IMAGE=my-registry/custom-upf:v2.0
export UPF_REPLICAS=2
python -m src.main
```

---

## 📝 Licence

[LICENSE](LICENSE) — voir le fichier pour plus de détails.

---

## 🤝 Contribution

Les contributions sont les bienvenues ! Pour contribuer :

1. Forkez le projet
2. Créez une branche pour votre feature (`git checkout -b feature/AmazingFeature`)
3. Committez vos changements (`git commit -m 'Add some AmazingFeature'`)
4. Pushez vers la branche (`git push origin feature/AmazingFeature`)
5. Ouvrez une Pull Request

---

## 🏆 Crédits

Projet basé sur :
- [AIDY-F2N/NexSlice](https://github.com/AIDY-F2N/NexSlice) pour le core 5G OAI
- [OpenAirInterface](https://www.openairinterface.org/) pour les composants 5G
- [UERANSIM](https://github.com/aligungr/UERANSIM) pour la simulation RAN
