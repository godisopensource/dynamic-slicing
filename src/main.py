from flask import Flask, render_template, redirect, url_for, jsonify
import os
from kubernetes import client
from kubernetes import config as k8s_config
import re

app = Flask(__name__)

# Configuration simple via variables d'environnement
UPF_IMAGE = os.environ.get("UPF_IMAGE", "free5gc/upf:latest")
try:
    UPF_REPLICAS = int(os.environ.get("UPF_REPLICAS", "1"))
except Exception:
    UPF_REPLICAS = 1

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

@app.route('/')
def hello():
    return render_template('index.html')

@app.route('/api/ue-count')
def ue_count():
    """API pour récupérer le nombre de UE créés"""
    count = get_last_ue_index()
    return jsonify({'count': count})

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

@app.route('/add_pod', methods=['POST'])
def add_pods():
    i = get_last_ue_index() + 1
    print(f"Génération du UE {i}...")
    generate_ue_config(i)
    create_ue_configmap(i)
    create_ue_pod(i)
    print(f"UE {i} généré (fichiers de config créés)")
    # Créer un UPF dédié pour ce nouvel UE
    try:
        create_upf_for_ue(i, image=UPF_IMAGE, replicas=UPF_REPLICAS)
    except Exception as e:
        print(f"Erreur lors de la création de l'UPF pour UE {i}: {e}")
    
    return redirect(url_for('hello'))

def generate_ue_config(ue_id):
    """Génère un fichier de configuration UERANSIM pour un UE"""
    # Padding pour avoir un IMSI unique (ex: 999700000000001)
    imsi = f"999700{ue_id:09d}"
    msisdn = f"{ue_id:010d}"
    
    config_content = f"""# UE Configuration for ue{ue_id}
supi: 'imsi-{imsi}'
mcc: '999'
mnc: '70'
key: '465B5CE8B199B49FAA5F0A2EE238A6BC'
op: 'E8ED289DEBA952E4283B54E88E6183CA'
opType: 'OPC'
amf: '8000'
imei: '{ue_id:015d}'
imeiSv: '{ue_id:016d}'

# List of gNB IP addresses for Radio Link Simulation
gnbSearchList:
  - ueransim-gnb

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
    apn: 'internet'
    slice:
      sst: 1
      sd: 0x111111

# Configured NSSAI for this UE by HPLMN
configured-nssai:
  - sst: 1
    sd: 0x111111

# Default Configured NSSAI for this UE
default-nssai:
  - sst: 1
    sd: 0x111111

# Supported encryption and integrity algorithms by this UE
integrity:
  IA1: true
  IA2: true
  IA3: true

ciphering:
  EA1: true
  EA2: true
  EA3: true
"""
    
    # Créer le dossier s'il n'existe pas
    os.makedirs("./tmp/ue-confs/", exist_ok=True)
    
    with open(f"./tmp/ue-confs/ue{ue_id}.yaml", "w") as f:
        f.write(config_content)

def create_ue_configmap(ue_id):
    """Crée un ConfigMap Kubernetes pour la configuration du UE"""
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
                f"ue{ue_id}.yaml": config_data
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
                    "command": ["/ueransim/build/nr-ue"],
                    "args": ["-c", f"/config/ue{ue_id}.yaml"],
                    "volumeMounts": [{
                        "name": "config-volume",
                        "mountPath": "/config"
                    }],
                    "securityContext": {
                        "capabilities": {
                            "add": ["NET_ADMIN"]
                        },
                        "privileged": False
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
                    "containers": [{
                        "name": "upf",
                        "image": image,
                        "imagePullPolicy": "IfNotPresent",
                        "ports": [{"containerPort": 2152, "name": "gtpu"}, {"containerPort": 8805, "name": "pfcp"}],
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
                {"protocol": "UDP", "port": 2152, "targetPort": "gtpu"},
                {"protocol": "UDP", "port": 8805, "targetPort": "pfcp"}
            ]
        }
    }

    return deployment, service


def create_upf_for_ue(ue_id, image="free5gc/upf:latest", replicas=1):
    """Crée une Deployment + Service UPF dédiée pour un UE.

    Note: l'image par défaut est un placeholder — changez-la pour une image UPF réelle
    adaptée à votre environnement (ex: free5gc/upf, upf-bess, etc.).
    """
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
    except Exception as e:
        print(f"Erreur lors de la création de l'UPF pour UE {ue_id}: {e}")
        return False
    return True


def delete_upf_for_ue(ue_id):
    """Supprime la Deployment et le Service UPF pour un UE si ils existent."""
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
