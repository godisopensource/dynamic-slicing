from flask import Flask
import os
from kubernetes import client, config

app = Flask(__name__)


@app.route('/')
def hello():
    return 'Hello Benoir'

def generate_ue_config(ue_id):
    config_content = f"""
    [NRUE]
    imsi = 20893000000000{ue_id}
    key = 00000000000000000000000000000000
    plmn = 20893
    slice = 1
    """
    with open(f"ue{ue_id}.conf", "w") as f:
        f.write(config_content)

# Générer 100 fichiers de configuration
for i in range(1, 101):
    generate_ue_config(i)



config.load_kube_config()
v1 = client.CoreV1Api()

def create_ue_pod(ue_id, image="oai/oai-nr-ue:latest"):
    pod_name = f"ue{ue_id}"
    pod_manifest = {
        "apiVersion": "v1",
        "kind": "Pod",
        "metadata": {"name": pod_name},
        "spec": {
            "containers": [{
                "name": "oai-nr-ue",
                "image": image,
                "args": ["-c", f"/configs/ue{ue_id}.conf"]
            }],
            "volumes": [{
                "name": "config-volume",
                "configMap": {
                    "name": f"ue{ue_id}-config"
                }
            }],
            "volumeMounts": [{
                "mountPath": "/configs",
                "name": "config-volume"
            }]
        }
    }
    v1.create_namespaced_pod(namespace="nexslice", body=pod_manifest)
    print(f"Pod {pod_name} créé avec succès.")

# Créer 100 Pods
for i in range(1, 101):
    create_ue_pod(i)
