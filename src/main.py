from flask import Flask, render_template, redirect, url_for, jsonify, request, Response
import os
from kubernetes import client
from kubernetes import config as k8s_config
import re
import requests
from prometheus_client import Gauge, Counter, generate_latest, CONTENT_TYPE_LATEST

app = Flask(__name__)

# Configuration simple via variables d'environnement
UPF_IMAGE = os.environ.get("UPF_IMAGE", "oaisoftwarealliance/oai-upf:latest")
try:
    UPF_REPLICAS = int(os.environ.get("UPF_REPLICAS", "1"))
except Exception:
    UPF_REPLICAS = 1
DEMO_MODE = os.environ.get("DEMO_MODE", "0").lower() in ("1", "true", "yes")

UE_GAUGE = Gauge('nexslice_active_ues', 'Nombre d\'UE configur\u00e9s (fichiers locaux)')
# Gauge for total UPFs present in the cluster (or approximated in DEMO_MODE)
UPF_GAUGE = Gauge('nexslice_upfs_total', 'Nombre total d\'UPF d\u00e9ploy\u00e9s')

def get_last_ue_index():
    """Récupère l'index du dernier fichier de configuration UE"""
    ue_conf_dir = "./tmp/ue-confs/"
    
    # Vérifier si le dossier existe
    if not os.path.exists(ue_conf_dir):
        return 0
    
    # Lister tous les fichiers dans le dossier
    files = os.listdir(ue_conf_dir)
    
    # Extraire les numéros des fichiers ue*.yaml
    ue_numbers = []
    for file in files:
        match = re.match(r'ue(\d+)\.yaml', file)
        if match:
            ue_numbers.append(int(match.group(1)))
    
    # Retourner le plus grand numéro ou 0 si aucun fichier
    return max(ue_numbers) if ue_numbers else 0


def refresh_ue_metrics():
    try:
        UE_GAUGE.set(get_last_ue_index())
    except Exception:
        pass


def get_upf_count():
    """Count UPF deployments in the cluster or approximate via local files in DEMO_MODE.

    Returns an integer count.
    """
    # In demo mode we approximate by counting local UE config files (one UPF per UE)
    if DEMO_MODE:
        ue_conf_dir = "./tmp/ue-confs/"
        if not os.path.exists(ue_conf_dir):
            return 0
        files = os.listdir(ue_conf_dir)
        cnt = 0
        for file in files:
            if re.match(r'ue(\d+)\.yaml', file):
                cnt += 1
        return cnt

    # In real mode, query Kubernetes for deployments labeled app=upf in namespace nexslice
    try:
        k8s_config.load_kube_config()
        apps_v1 = client.AppsV1Api()
        deps = apps_v1.list_namespaced_deployment(namespace="nexslice", label_selector="app=upf")
        return len(deps.items)
    except Exception:
        return 0


def refresh_upf_metrics():
    try:
        UPF_GAUGE.set(get_upf_count())
    except Exception:
        pass


def notify_smf_new_dnn(ue_id):
    """Notifie le SMF d'un nouveau mapping DNN → UPF via webhook.
    
    Cette fonction envoie une requête HTTP au SMF pour l'informer qu'un nouveau
    DNN a été créé et doit être routé vers l'UPF dédié correspondant.
    
    Le SMF doit exposer un endpoint webhook compatible avec ce format.
    """
    if DEMO_MODE:
        print(f"[DEMO_MODE] Skip SMF notification for UE {ue_id}")
        return True
    
    # URL du webhook SMF (à adapter selon votre déploiement)
    smf_webhook_url = os.environ.get(
        "SMF_WEBHOOK_URL",
        "http://oai-smf.nexslice.svc.cluster.local:8080/api/dnn/register"
    )
    
    payload = {
        "dnn": f"oai-ue{ue_id}",
        "upf_fqdn": f"upf-ue{ue_id}.nexslice.svc.cluster.local",
        "upf_port": 8805,  # Port PFCP
        "ip_range": f"12.1.{ue_id}.0/24",
        "sst": 1,
        "sd": f"{ue_id:06d}",
        "pdu_session_type": "IPv4"
    }
    
    try:
        response = requests.post(
            smf_webhook_url,
            json=payload,
            timeout=5,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code in [200, 201, 204]:
            print(f"✓ SMF notifié : oai-ue{ue_id} → upf-ue{ue_id} (Status: {response.status_code})")
            return True
        else:
            print(f"⚠ SMF webhook status {response.status_code}: {response.text}")
            return False
            
    except requests.exceptions.Timeout:
        print(f"⚠ Timeout lors de la notification SMF pour UE {ue_id}")
        return False
    except requests.exceptions.ConnectionError:
        print(f"⚠ SMF webhook non disponible (vérifier que le service est accessible)")
        return False
    except Exception as e:
        print(f"Erreur notification SMF: {e}")
        return False


@app.route('/')
def hello():
    return render_template('index.html')

@app.route('/api/ue-count')
def ue_count():
    """API pour récupérer le nombre de UE créés"""
    count = get_last_ue_index()
    return jsonify({'count': count})

@app.route('/api/ue-list')
def ue_list():
    """API pour récupérer la liste des UE actifs"""
    ue_conf_dir = "./tmp/ue-confs/"
    
    if not os.path.exists(ue_conf_dir):
        return jsonify({'ues': []})
    
    files = os.listdir(ue_conf_dir)
    ue_ids = []
    
    for file in files:
        match = re.match(r'ue(\d+)\.yaml', file)
        if match:
            ue_ids.append(int(match.group(1)))
    
    ue_ids.sort()
    return jsonify({'ues': ue_ids})

@app.route('/create_pods', methods=['POST'])
def create_pods():
    # Générer 100 UE UERANSIM
    for i in range(1, 101):
        generate_ue_config(i)
        create_ue_configmap(i)
        create_ue_pod(i)
        # Créer un UPF dédié pour cet UE
        try:
            create_upf_for_ue(i, image=UPF_IMAGE, replicas=UPF_REPLICAS)
        except Exception as e:
            print(f"Erreur lors de la création de l'UPF pour UE {i}: {e}")
    
    return redirect(url_for('hello'))


@app.route('/delete_pods', methods=['POST'])
def delete_pods():
    """Supprime les 100 UEs/UPFs créés par le bouton de génération.

    Itère sur les IDs 1..100 et supprime le fichier de config local, le Pod
    UERANSIM, le ConfigMap et l'UPF (Deployment + Service). Ignore les erreurs
    individuelles afin que l'opération soit idempotente.
    """
    start = 1
    end = 100
    for i in range(start, end + 1):
        # supprimer fichier local
        config_file = f"./tmp/ue-confs/ue{i}.yaml"
        if os.path.exists(config_file):
            try:
                os.remove(config_file)
                print(f"Fichier {config_file} supprimé.")
            except Exception as e:
                print(f"Erreur suppression fichier {config_file}: {e}")

        # supprimer ressources Kubernetes (pod, configmap, deployment, service)
        if DEMO_MODE:
            # In demo mode, just increment deletion counter and continue
            UPF_DELETE_COUNTER.inc()
            refresh_ue_metrics()
            continue

        try:
            k8s_config.load_kube_config()
            v1 = client.CoreV1Api()
            apps_v1 = client.AppsV1Api()

            pod_name = f"ueransim-ue{i}"
            configmap_name = f"ueransim-ue{i}-config"
            upf_name = f"upf-ue{i}"

            try:
                v1.delete_namespaced_pod(name=pod_name, namespace="nexslice")
                print(f"Pod {pod_name} supprimé.")
            except Exception:
                pass

            try:
                v1.delete_namespaced_config_map(name=configmap_name, namespace="nexslice")
                print(f"ConfigMap {configmap_name} supprimé.")
            except Exception:
                pass

            try:
                apps_v1.delete_namespaced_deployment(name=upf_name, namespace="nexslice")
                print(f"Deployment {upf_name} supprimé.")
            except Exception:
                pass

            try:
                v1.delete_namespaced_service(name=upf_name, namespace="nexslice")
                print(f"Service {upf_name} supprimé.")
            except Exception:
                pass

            UPF_DELETE_COUNTER.inc()
            refresh_ue_metrics()
        except Exception as e:
            print(f"Erreur lors de la suppression des ressources pour UE {i}: {e}")

    return redirect(url_for('hello'))

@app.route('/add_pod', methods=['POST'])
def add_pods():
    i = get_last_ue_index() + 1
    print(f"Génération du UE {i}...")
    
    # 1. Générer config UE avec DNN unique
    generate_ue_config(i)
    
    # 2. Créer un UPF dédié pour ce nouvel UE
    try:
        create_upf_for_ue(i, image=UPF_IMAGE, replicas=UPF_REPLICAS)
    except Exception as e:
        print(f"Erreur lors de la création de l'UPF pour UE {i}: {e}")
    
    # 3. Notifier le SMF du nouveau mapping DNN → UPF
    notify_smf_new_dnn(i)
    
    # 4. Créer les ressources UE (ConfigMap et Pod)
    create_ue_configmap(i)
    create_ue_pod(i)
    print(f"UE {i} généré (fichiers de config créés)")
    
    return redirect(url_for('hello'))

def generate_ue_config(ue_id):
    """Génère un fichier de configuration UERANSIM pour un UE"""
    # Padding pour avoir un IMSI unique (ex: 208950000000001)
    imsi = f"20895{ue_id:010d}"
    msisdn = f"{ue_id:010d}"
    
    config_content = f"""# UE Configuration for ue{ue_id}
supi: 'imsi-{imsi}'
mcc: '208'
mnc: '95'
key: '465B5CE8B199B49FAA5F0A2EE238A6BC'
op: 'E8ED289DEBA952E4283B54E88E6183CA'
opType: 'OPC'
amf: '8000'
imei: '{ue_id:015d}'
imeiSv: '{ue_id:016d}'

# List of gNB IP addresses for Radio Link Simulation
# Use pod name directly for radio link simulation (not service)
gnbSearchList:
  - ueransim-gnb.nexslice.svc.cluster.local

# UAC Access Identities Configuration
uacAic:
  mps: false
  mcs: false

# UAC Access Control Class
uacAcc:
  normalClass: 0
  class11: false
  class12: false
  class13: false
  class14: false
  class15: false

# Initial PDU sessions to be established
sessions:
  - type: 'IPv4'
    apn: 'oai-ue{ue_id}'
    slice:
      sst: 1
      sd: {ue_id:06d}

# Configured NSSAI for this UE by HPLMN
configured-nssai:
  - sst: 1
    sd: {ue_id:06d}

# Default Configured NSSAI for this UE
default-nssai:
  - sst: 1
    sd: {ue_id:06d}

# Supported encryption and integrity algorithms by this UE
integrity:
  IA1: true
  IA2: true
  IA3: true

integrityMaxRate:
  uplink: 'full'
  downlink: 'full'

ciphering:
  EA1: true
  EA2: true
  EA3: true
"""
    
    # Créer le dossier s'il n'existe pas
    os.makedirs("./tmp/ue-confs/", exist_ok=True)
    
    with open(f"./tmp/ue-confs/ue{ue_id}.yaml", "w") as f:
        f.write(config_content)
    refresh_ue_metrics()

def create_ue_configmap(ue_id):
    """Crée un ConfigMap Kubernetes pour la configuration du UE"""
    if DEMO_MODE:
        print(f"[DEMO_MODE] Skip ConfigMap creation for UE {ue_id}.")
        return True
    try:
        k8s_config.load_kube_config()
        v1 = client.CoreV1Api()
        
        # Lire le fichier de configuration
        with open(f"./tmp/ue-confs/ue{ue_id}.yaml", "r") as f:
            config_data = f.read()
        
        configmap_name = f"ueransim-ue{ue_id}-config"
        configmap = {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": {
                "name": configmap_name,
                "namespace": "nexslice"
            },
            "data": {
                # UERANSIM entrypoint expects /etc/ueransim/ue.yaml (hardcoded)
                "ue.yaml": config_data
            }
        }
        
        v1.create_namespaced_config_map(namespace="nexslice", body=configmap)
        print(f"ConfigMap {configmap_name} créé avec succès.")
    except Exception as e:
        print(f"Erreur lors de la création du ConfigMap: {e}")
        # En mode dev sans Kubernetes, on continue sans créer le ConfigMap
        return False
    return True

def create_ue_pod(ue_id, image="gradiant/ueransim:3.2.6"):
    """Crée un Pod UERANSIM pour simuler un UE"""
    if DEMO_MODE:
        print(f"[DEMO_MODE] Skip Pod creation for UE {ue_id}.")
        return True
    try:
        # Charger la config Kubernetes uniquement quand nécessaire
        k8s_config.load_kube_config()
        v1 = client.CoreV1Api()
        
        pod_name = f"ueransim-ue{ue_id}"
        configmap_name = f"ueransim-ue{ue_id}-config"
        
        pod_manifest = {
            "apiVersion": "v1",
            "kind": "Pod",
            "metadata": {
                "name": pod_name,
                "namespace": "nexslice",
                "labels": {
                    "app": "ueransim-ue",
                    "ue-id": str(ue_id)
                }
            },
                "spec": {
                "containers": [{
                    "name": "ueransim-ue",
                    "image": image,
                    "imagePullPolicy": "Always",
                    # UERANSIM entrypoint expects: <component> <config-file>
                    # where component is 'ue' or 'gnb'
                    "args": ["ue", "/etc/ueransim/ue.yaml"],
                    "volumeMounts": [{
                        "name": "config-volume",
                        "mountPath": "/etc/ueransim"
                    }],
                    "securityContext": {
                        "capabilities": {
                            "add": ["NET_ADMIN"]
                        },
                        "privileged": True
                    }
                }],
                "volumes": [{
                    "name": "config-volume",
                    "configMap": {
                        "name": configmap_name
                    }
                }],
                "restartPolicy": "Always"
            }
        }
        
        v1.create_namespaced_pod(namespace="nexslice", body=pod_manifest)
        print(f"Pod {pod_name} créé avec succès.")
    except Exception as e:
        print(f"Erreur lors de la création du Pod: {e}")
        # En mode dev sans Kubernetes, on continue sans créer le Pod
        return False
    return True


def make_upf_deployment_and_service(name, labels, image, replicas):
    """Return a (deployment, service) tuple for an UPF named `name`.

    Includes minimal resource requests/limits to avoid noisy-neighbor issues in cluster.
    """
    deployment = {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {"name": name, "namespace": "nexslice"},
        "spec": {
            "replicas": replicas,
            "selector": {"matchLabels": labels},
            "template": {
                "metadata": {"labels": labels},
                "spec": {
                    "volumes": [{
                        "name": "configuration",
                        "configMap": {
                            "name": "oai-upf-configmap"
                        }
                    }],
                    "containers": [{
                        "name": "upf",
                        "image": image,
                        "imagePullPolicy": "IfNotPresent",
                        "ports": [{"containerPort": 2152, "name": "gtpu"}, {"containerPort": 8805, "name": "pfcp"}],
                        "env": [
                            {"name": "TZ", "value": "Europe/Paris"},
                            {"name": "ENABLE_5G_FEATURES", "value": "yes"},
                            {"name": "REGISTER_NRF", "value": "no"}
                        ],
                        "volumeMounts": [{
                            "name": "configuration",
                            "mountPath": "/openair-upf/etc"
                        }],
                        "securityContext": {
                            "capabilities": {"add": ["NET_ADMIN", "SYS_ADMIN"]},
                            "privileged": True
                        },
                        "resources": {
                            "requests": {"cpu": "100m", "memory": "128Mi"},
                            "limits": {"cpu": "500m", "memory": "512Mi"}
                        }
                    }]
                }
            }
        }
    }

    service = {
        "apiVersion": "v1",
        "kind": "Service",
        "metadata": {"name": name, "namespace": "nexslice"},
        "spec": {
            "selector": labels,
            "ports": [
                {"protocol": "UDP", "port": 2152, "targetPort": "gtpu", "name": "gtpu"},
                {"protocol": "UDP", "port": 8805, "targetPort": "pfcp", "name": "pfcp"}
            ]
        }
    }

    return deployment, service


def create_upf_for_ue(ue_id, image="free5gc/upf:latest", replicas=1):
    """Crée une Deployment + Service UPF dédiée pour un UE.

    Note: l'image par défaut est un placeholder — changez-la pour une image UPF réelle
    adaptée à votre environnement (ex: free5gc/upf, upf-bess, etc.).
    """
    if DEMO_MODE:
        print(f"[DEMO_MODE] Pretend creating UPF upf-ue{ue_id} (no Kubernetes API call).")
        # Update gauge approximation
        refresh_upf_metrics()
        return True
    try:
        k8s_config.load_kube_config()
        apps_v1 = client.AppsV1Api()
        v1 = client.CoreV1Api()

        name = f"upf-ue{ue_id}"
        labels = {"app": "upf", "ue-id": str(ue_id)}

        deployment, service = make_upf_deployment_and_service(name, labels, image, replicas)

        apps_v1.create_namespaced_deployment(namespace="nexslice", body=deployment)
        v1.create_namespaced_service(namespace="nexslice", body=service)
        print(f"UPF {name} (Deployment+Service) créé pour UE {ue_id}.")
        # Refresh gauge to reflect the new UPF
        refresh_upf_metrics()
    except Exception as e:
        print(f"Erreur lors de la création de l'UPF pour UE {ue_id}: {e}")
        return False
    return True


def delete_upf_for_ue(ue_id):
    """Supprime la Deployment et le Service UPF pour un UE si ils existent."""
    if DEMO_MODE:
        print(f"[DEMO_MODE] Pretend deleting UPF upf-ue{ue_id} (no Kubernetes API call).")
        # Update gauge approximation
        refresh_upf_metrics()
        return True
    try:
        k8s_config.load_kube_config()
        apps_v1 = client.AppsV1Api()
        v1 = client.CoreV1Api()

        name = f"upf-ue{ue_id}"

        # Delete deployment (ignore if not found)
        try:
            apps_v1.delete_namespaced_deployment(name=name, namespace="nexslice")
            print(f"Deployment {name} supprimé.")
        except Exception:
            pass

        # Delete service
        try:
            v1.delete_namespaced_service(name=name, namespace="nexslice")
            print(f"Service {name} supprimé.")
        except Exception:
            pass
        # Refresh gauge to reflect deletion
        refresh_upf_metrics()
    except Exception as e:
        print(f"Erreur lors de la suppression de l'UPF pour UE {ue_id}: {e}")
        return False
    return True


@app.route('/remove_pod/<int:ue_id>', methods=['POST'])
def remove_pod(ue_id):
    """Supprime le Pod UE, le ConfigMap associé et l'UPF dédié.

    Cette route permet de simuler la déconnexion d'un UE et libérer les
    ressources UPF associées.
    """
    # Supprimer le fichier de configuration local
    config_file = f"./tmp/ue-confs/ue{ue_id}.yaml"
    if os.path.exists(config_file):
        os.remove(config_file)
        refresh_ue_metrics()
        print(f"Fichier {config_file} supprimé.")
        refresh_ue_metrics()
    
    # Supprimer le Pod
    try:
        k8s_config.load_kube_config()
        v1 = client.CoreV1Api()
        pod_name = f"ueransim-ue{ue_id}"
        configmap_name = f"ueransim-ue{ue_id}-config"

        try:
            v1.delete_namespaced_pod(name=pod_name, namespace="nexslice")
            print(f"Pod {pod_name} supprimé.")
        except Exception:
            print(f"Pod {pod_name} non trouvé ou erreur lors de la suppression.")

        # Supprimer ConfigMap
        try:
            v1.delete_namespaced_config_map(name=configmap_name, namespace="nexslice")
            print(f"ConfigMap {configmap_name} supprimé.")
        except Exception:
            print(f"ConfigMap {configmap_name} non trouvé ou erreur lors de la suppression.")

        # Supprimer l'UPF
        delete_upf_for_ue(ue_id)
    except Exception as e:
        print(f"Erreur lors de la suppression des ressources pour UE {ue_id}: {e}")

    return redirect(url_for('hello'))


@app.route('/api/ue-disconnect', methods=['POST'])
def ue_disconnect():
    """Webhook simplifié pour signaler la déconnexion d'un UE.

    Corps JSON attendu:
    {"ue_id": 1}

    Supprime les ressources UE locales (fichier de config, Pod, ConfigMap)
    ainsi que l'UPF dédié.
    """
    data = request.get_json(silent=True) or {}
    ue_id = data.get("ue_id")
    if not isinstance(ue_id, int) or ue_id <= 0:
        return jsonify({"error": "ue_id entier positif requis"}), 400

    # Réutiliser la logique existante de remove_pod
    config_file = f"./tmp/ue-confs/ue{ue_id}.yaml"
    if os.path.exists(config_file):
        os.remove(config_file)
        refresh_ue_metrics()

    try:
        k8s_config.load_kube_config()
        v1 = client.CoreV1Api()
        pod_name = f"ueransim-ue{ue_id}"
        configmap_name = f"ueransim-ue{ue_id}-config"

        try:
            v1.delete_namespaced_pod(name=pod_name, namespace="nexslice")
        except Exception:
            pass

        try:
            v1.delete_namespaced_config_map(name=configmap_name, namespace="nexslice")
        except Exception:
            pass

        delete_upf_for_ue(ue_id)
    except Exception as e:
        print(f"Erreur lors de la suppression des ressources pour UE {ue_id}: {e}")
        return jsonify({"error": "erreur de suppression des ressources"}), 500

    return jsonify({"status": "ok", "ue_id": ue_id}), 200


@app.route('/api/ue-connect', methods=['POST'])
def ue_connect():
    """Webhook simplifié pour signaler la connexion d'un UE.

    Corps JSON attendu (exemple minimal):
    {"ue_id": 1}

    Dans un système complet, cet endpoint pourrait être appelé par
    Alertmanager, un opérateur 5G ou un autre composant lorsqu'un
    événement de connexion UE est détecté.
    """
    data = request.get_json(silent=True) or {}
    ue_id = data.get("ue_id")
    if not isinstance(ue_id, int) or ue_id <= 0:
        return jsonify({"error": "ue_id entier positif requis"}), 400

    # Générer configuration et ressources UE si nécessaire
    generate_ue_config(ue_id)
    create_ue_configmap(ue_id)
    create_ue_pod(ue_id)

    # Créer UPF dédié
    ok = create_upf_for_ue(ue_id, image=UPF_IMAGE, replicas=UPF_REPLICAS)
    if not ok:
        return jsonify({"error": f"échec création UPF pour UE {ue_id}"}), 500

    return jsonify({"status": "ok", "ue_id": ue_id}), 200


@app.route('/metrics')
def metrics():
    """Expose les métriques Prometheus."""
    refresh_ue_metrics()
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)


if __name__ == "__main__":
    # Permet de configurer l'hôte et le port via les variables d'environnement
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "5000"))
    debug = os.environ.get("FLASK_DEBUG", "0") in ("1", "true", "True")
    print(f"Starting Flask on {host}:{port} (debug={debug})")
    app.run(host=host, port=port, debug=debug)
