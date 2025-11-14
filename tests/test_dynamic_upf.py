import os
import time
import requests
import pytest
from kubernetes import client, config

# Activate demo mode by default for tests so we don't depend on a live cluster unless specified.
os.environ.setdefault("DEMO_MODE", "1")

API_BASE = os.environ.get('API_BASE', 'http://localhost:5000')
NAMESPACE = 'nexslice'


def test_create_and_delete_upf():
    # Ensure kubeconfig is available and valid. If not, skip the integration test.
    try:
        config.load_kube_config()
    except Exception as e:
        pytest.skip(f"Skipping test because kubeconfig not available/invalid: {e}")
    v1 = client.AppsV1Api()
    core = client.CoreV1Api()

    # Create a UE via add_pod
    r = requests.post(f"{API_BASE}/add_pod")
    assert r.status_code in (200, 302)

    # Get last UE id
    r = requests.get(f"{API_BASE}/api/ue-count")
    assert r.status_code == 200
    ue_id = r.json()['count']

    name = f"upf-ue{ue_id}"

    # Wait for deployment to appear
    for _ in range(10):
        try:
            dep = v1.read_namespaced_deployment(name=name, namespace=NAMESPACE)
            break
        except Exception:
            time.sleep(1)
    else:
        raise AssertionError("UPF deployment not created")

    # Now delete
    r = requests.post(f"{API_BASE}/remove_pod/{ue_id}")
    assert r.status_code in (200, 302)

    # Wait and assert deletion
    for _ in range(8):
        try:
            v1.read_namespaced_deployment(name=name, namespace=NAMESPACE)
            time.sleep(1)
        except Exception:
            # expected not found
            return
    raise AssertionError("UPF deployment still exists after deletion")
