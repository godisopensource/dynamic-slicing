# Guide d'Intégration SMF ↔ NexSlice

## Contexte

NexSlice implémente un système de **slicing dynamique 1:1** où chaque UE dispose de son propre UPF dédié. Pour que cette isolation soit effective au niveau du plan de données 5G, le SMF (Session Management Function) doit router chaque UE vers son UPF spécifique.

Cette intégration repose sur un **webhook HTTP** que le SMF doit exposer pour recevoir les notifications de NexSlice lors de la création d'un nouveau couple UE/UPF.

---

## Architecture de Communication

```
NexSlice Controller (Flask)
        ↓
    [POST] Webhook HTTP
        ↓
SMF (Session Management Function)
        ↓
    Configuration DNN → UPF
        ↓
    Routage des sessions PDU
```

---

## Spécification du Webhook SMF

### Endpoint à Exposer

Le SMF doit exposer un endpoint HTTP accessible depuis le cluster Kubernetes :

**URL par défaut** : `http://oai-smf.nexslice.svc.cluster.local:8080/api/dnn/register`

> Cette URL peut être configurée via la variable d'environnement `SMF_WEBHOOK_URL` dans le contrôleur NexSlice.

---

### Format de la Requête

**Méthode** : `POST`  
**Content-Type** : `application/json`

**Body JSON** :

```json
{
  "dnn": "oai-ue1",
  "upf_fqdn": "upf-ue1.nexslice.svc.cluster.local",
  "upf_port": 8805,
  "ip_range": "12.1.1.0/24",
  "sst": 1,
  "sd": "000001",
  "pdu_session_type": "IPv4"
}
```

**Champs** :

| Champ | Type | Description | Exemple |
|-------|------|-------------|---------|
| `dnn` | `string` | Data Network Name unique pour cet UE | `"oai-ue1"` |
| `upf_fqdn` | `string` | FQDN du Service Kubernetes de l'UPF dédié | `"upf-ue1.nexslice.svc.cluster.local"` |
| `upf_port` | `int` | Port PFCP de l'UPF (par défaut 8805) | `8805` |
| `ip_range` | `string` | Plage IP CIDR à allouer pour ce DNN | `"12.1.1.0/24"` |
| `sst` | `int` | Slice Service Type (toujours 1 pour NexSlice) | `1` |
| `sd` | `string` | Slice Differentiator unique (6 chiffres, ex: `"000001"` pour UE 1) | `"000001"` |
| `pdu_session_type` | `string` | Type de session PDU (IPv4 ou IPv6) | `"IPv4"` |

---

### Réponse Attendue

Le SMF doit répondre avec l'un des codes HTTP suivants :

| Code | Signification | Action NexSlice |
|------|---------------|-----------------|
| **200** | Mapping enregistré avec succès | ✅ Continue le déploiement |
| **201** | Ressource créée | ✅ Continue le déploiement |
| **204** | Pas de contenu (OK) | ✅ Continue le déploiement |
| **400** | Erreur dans le format JSON | ⚠️ Log l'erreur |
| **409** | DNN déjà existant | ⚠️ Log l'avertissement |
| **500** | Erreur interne SMF | ⚠️ Log l'erreur |
| **Timeout** | SMF non accessible | ⚠️ Continue sans notification |

**Exemple de réponse (optionnel)** :

```json
{
  "status": "registered",
  "dnn": "oai-ue1",
  "upf_fqdn": "upf-ue1.nexslice.svc.cluster.local"
}
```

---

## Implémentation Côté SMF

### Option A : OAI-SMF (OpenAirInterface)

Si vous utilisez OAI-SMF, voici un exemple de patch à appliquer :

**Fichier : `src/api/smf_http_server.cpp`** (ou équivalent)

```cpp
// Ajouter un endpoint pour le webhook NexSlice
void register_dnn_mapping(const httplib::Request &req, httplib::Response &res) {
    nlohmann::json body = nlohmann::json::parse(req.body);
    
    std::string dnn = body["dnn"];
    std::string upf_fqdn = body["upf_fqdn"];
    int upf_port = body["upf_port"];
    std::string ip_range = body["ip_range"];
    
    // Ajouter le mapping dans la configuration interne du SMF
    dnn_configuration_t dnn_config;
    dnn_config.dnn = dnn;
    dnn_config.upf_list.push_back({upf_fqdn, upf_port});
    dnn_config.pdu_session_type = PDU_SESSION_TYPE_IPV4;
    dnn_config.ipv4_pool = ip_range;
    
    smf_app_inst->add_dnn_configuration(dnn_config);
    
    Logger::smf_api_server().info("✓ DNN %s registered → UPF %s", dnn.c_str(), upf_fqdn.c_str());
    
    res.status = 201;
    res.set_content("{\"status\":\"registered\"}", "application/json");
}

// Dans la fonction main() du serveur HTTP
server.Post("/api/dnn/register", register_dnn_mapping);
```

---

### Option B : Free5GC SMF

Pour Free5GC, la configuration est plus déclarative. Créer un script d'API :

**Fichier : `scripts/dnn_webhook_handler.go`**

```go
package main

import (
    "encoding/json"
    "net/http"
    "github.com/free5gc/smf/internal/context"
)

type DNNRegistration struct {
    DNN             string `json:"dnn"`
    UPFFQDN         string `json:"upf_fqdn"`
    UPFPort         int    `json:"upf_port"`
    IPRange         string `json:"ip_range"`
    SST             int    `json:"sst"`
    SD              string `json:"sd"`
    PDUSessionType  string `json:"pdu_session_type"`
}

func handleDNNRegister(w http.ResponseWriter, r *http.Request) {
    var reg DNNRegistration
    json.NewDecoder(r.Body).Decode(&reg)
    
    // Ajouter la config DNN dynamiquement
    dnnConfig := context.DNNConfiguration{
        Dnn: reg.DNN,
        PduSessionTypes: []string{reg.PDUSessionType},
        SscModes: []string{"SSC_MODE_1"},
        IpPools: []string{reg.IPRange},
    }
    
    context.GetSelf().DNNConfigurations[reg.DNN] = &dnnConfig
    
    w.WriteHeader(http.StatusCreated)
    json.NewEncoder(w).Encode(map[string]string{"status": "registered"})
}

func main() {
    http.HandleFunc("/api/dnn/register", handleDNNRegister)
    http.ListenAndServe(":8080", nil)
}
```

---

### Option C : Script Externe (Si modification SMF impossible)

Si vous ne pouvez pas modifier le code du SMF, créer un **sidecar container** qui expose le webhook et met à jour la ConfigMap du SMF :

**Fichier : `k8s/smf-webhook-sidecar.yaml`**

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: oai-smf
spec:
  template:
    spec:
      containers:
        # Container SMF principal (inchangé)
        - name: smf
          image: oaisoftwarealliance/oai-smf:latest
          # ... config existante ...
        
        # Sidecar pour le webhook
        - name: nexslice-webhook
          image: python:3.11-slim
          command: ["python", "/app/webhook_handler.py"]
          ports:
            - containerPort: 8080
          volumeMounts:
            - name: smf-config
              mountPath: /etc/oai-smf
            - name: webhook-script
              mountPath: /app
      volumes:
        - name: smf-config
          configMap:
            name: oai-smf-config
        - name: webhook-script
          configMap:
            name: nexslice-webhook-script
```

**Script du sidecar : `webhook_handler.py`**

```python
from flask import Flask, request, jsonify
import subprocess

app = Flask(__name__)

@app.route('/api/dnn/register', methods=['POST'])
def register_dnn():
    data = request.json
    dnn = data['dnn']
    upf_fqdn = data['upf_fqdn']
    ip_range = data['ip_range']
    
    # Ajouter une entrée dans la config SMF
    with open('/etc/oai-smf/smf.conf', 'a') as f:
        f.write(f'\n# Auto-generated by NexSlice\n')
        f.write(f'DNN_{dnn.upper()} = {{\n')
        f.write(f'  DNN_NI = "{dnn}";\n')
        f.write(f'  PDU_SESSION_TYPE = "IPv4";\n')
        f.write(f'  IPV4_RANGE = "{ip_range}";\n')
        f.write(f'  UPF_LIST = ({{UPF_FQDN = "{upf_fqdn}";}});\n')
        f.write(f'}};\n')
    
    # Envoyer SIGHUP au SMF pour recharger la config
    subprocess.run(['killall', '-HUP', 'oai_smf'])
    
    return jsonify({'status': 'registered'}), 201

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
```

---

## Tests et Validation

### 1. Vérifier que le webhook est accessible

Depuis un Pod du cluster :

```bash
kubectl run -it --rm debug --image=curlimages/curl --restart=Never -- \
  curl -X POST http://oai-smf.nexslice.svc.cluster.local:8080/api/dnn/register \
  -H "Content-Type: application/json" \
  -d '{"dnn":"test-ue1","upf_fqdn":"upf-ue1.nexslice.svc.cluster.local","upf_port":8805,"ip_range":"12.1.1.0/24","sst":1,"sd":"000001","pdu_session_type":"IPv4"}'
```

**Réponse attendue** : `{"status":"registered"}` avec code HTTP 201.

---

### 2. Vérifier les logs du SMF

Après avoir créé un UE via NexSlice, vérifier que le SMF a bien reçu la notification :

```bash
kubectl logs -n nexslice -l app=oai-smf | grep "DNN.*registered"
```

Vous devriez voir :

```
[INFO] ✓ DNN oai-ue1 registered → UPF upf-ue1.nexslice.svc.cluster.local
```

---

### 3. Valider le routage UE → UPF

1. Créer un UE via l'interface NexSlice : `POST /add_pod`
2. Attendre que l'UE s'enregistre (logs UERANSIM)
3. Vérifier le tunnel GTP-U :

```bash
# Sur le Pod UPF
kubectl exec -n nexslice upf-ue1-xxxx -- tcpdump -i any port 2152 -n
```

4. Générer du trafic depuis l'UE :

```bash
kubectl exec -n nexslice ueransim-ue1 -- ping -c 3 8.8.8.8
```

5. Confirmer que les paquets GTP passent bien par `upf-ue1` et non un autre UPF.

---

## Configuration de l'URL du Webhook

Par défaut, NexSlice utilise l'URL : `http://oai-smf.nexslice.svc.cluster.local:8080/api/dnn/register`

Pour la modifier, définir la variable d'environnement dans le déploiement du contrôleur :

**Fichier : `k8s/controller-deployment.yaml`**

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: nexslice-controller
spec:
  template:
    spec:
      containers:
        - name: controller
          image: nexslice/controller:latest
          env:
            - name: SMF_WEBHOOK_URL
              value: "http://mon-smf-custom.namespace.svc.cluster.local:9090/webhook/dnn"
```

---

## Troubleshooting

### Le SMF ne reçoit pas les notifications

**Vérifier la connectivité réseau** :

```bash
kubectl exec -n nexslice deployment/nexslice-controller -- \
  curl -v http://oai-smf.nexslice.svc.cluster.local:8080/api/dnn/register
```

**Logs du contrôleur** :

```bash
kubectl logs -n nexslice -l app=nexslice-controller | grep "SMF"
```

Chercher les messages :
- `✓ SMF notifié : oai-ue1 → upf-ue1` (succès)
- `⚠ SMF webhook non disponible` (erreur de connexion)
- `⚠ Timeout lors de la notification SMF` (timeout)

---

### Le SMF ne route pas vers le bon UPF

**Vérifier la config DNN du SMF** :

```bash
kubectl exec -n nexslice -it deployment/oai-smf -- cat /etc/oai-smf/smf.conf | grep "oai-ue"
```

Vous devriez voir les entrées DNN dynamiques ajoutées.

**Forcer le rechargement de la config** :

```bash
kubectl rollout restart deployment/oai-smf -n nexslice
```

---

## Résumé pour l'Équipe Cœur 5G

**Ce que NexSlice fournit** :
- ✅ Notifications webhook automatiques à chaque création d'UE
- ✅ Format JSON standardisé avec tous les paramètres nécessaires
- ✅ Gestion des erreurs et timeouts gracieusement

**Ce dont nous avons besoin** :
- ⚠️ Exposition d'un endpoint HTTP POST sur le SMF
- ⚠️ Ajout dynamique des mappings DNN → UPF dans la configuration SMF
- ⚠️ Rechargement à chaud de la config (ou redémarrage rapide du SMF)

**Alternative si modification SMF impossible** :
- Déploiement d'un sidecar container qui gère le webhook et met à jour la ConfigMap

---

## Contact

Pour toute question sur cette intégration, contacter l'équipe NexSlice :
- **GitHub Issues** : https://github.com/godisopensource/dynamic-slicing/issues
- **Documentation** : https://github.com/godisopensource/dynamic-slicing/tree/main/docs
