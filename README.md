# dynamic-slicing (NexSlice)

Contrôleur custom de **slicing dynamique** pour NexSlice : ce projet illustre, de manière simplifiée, la création et la suppression automatiques d’un UPF dédié par UE dans Kubernetes.

## Contexte et objectif

Dans l’état actuel de NexSlice, le slicing est statique : les VNFs (SMF, UPF) sont déployées à l’avance et associées aux slices. L’objectif de ce projet est de démontrer un **slicing dynamique simplifié** :

- Lorsqu’un UE se connecte au gNB, un nouvel UPF dédié est créé automatiquement pour ce slice.
- Lorsqu’un UE se déconnecte, l’UPF correspondant est supprimé pour libérer les ressources.

Pour rester simple, le projet ne gère que la création/suppression d’UPF (pas de SMF dynamique).

## Positionnement dans l’état de l’art

Ce projet correspond à la brique « contrôleur custom » recommandée dans l’état de l’art :

- **Socle 5G** : un opérateur comme `open5gs-operator` ou une stack Helm (`towards5gs-helm`) déploie le cœur 5G (AMF, SMF, UPF, etc.) de manière déclarative via des CRDs.
- **Contrôleur custom NexSlice (ce repo)** : réagit à des événements de connexion/déconnexion d’UE (simulés via API HTTP) pour créer/supprimer dynamiquement des ressources Kubernetes d’UPF (Deployment + Service) par UE ou par slice.
- **Évolution possible** : intégration avec Prometheus / Alertmanager / KEDA pour piloter le scaling en fonction de métriques (UEs par slice, charge UPF, messages N4, etc.).

Dans une architecture complète, les événements UE pourraient provenir :

- du cœur 5G (via logs, webhooks, CRDs mis à jour par `open5gs-operator`),
- d’Alertmanager (modèle Prometheus + webhook Python),
- ou d’un opérateur dédié. Ici, ils sont simplement simulés via des endpoints HTTP.

## Vue d’ensemble du projet

Ce dépôt contient :

- Une petite application Flask qui expose des endpoints pour :
	- créer un UE de test (Pod UERANSIM + ConfigMap),
	- créer un UPF dédié (Deployment + Service) pour cet UE,
	- supprimer l’UE et les ressources UPF associées.
- Un test d’intégration qui vérifie que la création/suppression d’UPF fonctionne bien.

Diagramme logique simplifié :

```
UE connexion (simulée)  → App Flask NexSlice (contrôleur custom)
												 → API Kubernetes :
														 - ConfigMap + Pod UERANSIM
														 - Deployment + Service UPF dédié

UE déconnexion (simulée) → App Flask NexSlice
												 → Suppression Pod/ConfigMap UE + UPF
```

## Quickstart

Prérequis :

- Un cluster Kubernetes et un kubeconfig fonctionnel,
- `kubectl` installé,
- Python 3.11+ et `pip`.

1. Installer les dépendances Python :

	python -m pip install -r requirements.txt

2. Lancer l’application Flask (depuis la racine du repo) :

	python -m src.main

3. Utiliser le script de démo pour créer un UE et vérifier la création de l’UPF (le script utilise `kubectl`) :

	./scripts/demo.sh 1

## Endpoints principaux

- `POST /add_pod` :
	- Simule une connexion UE.
	- Génère la configuration UERANSIM, crée un ConfigMap, crée un Pod UE et crée un UPF dédié (`Deployment` + `Service`) pour cet UE.

- `POST /remove_pod/<ue_id>` :
	- Simule une déconnexion UE.
	- Supprime le Pod UE, le ConfigMap associé et l’UPF (Deployment + Service) correspondant.

- `GET /api/ue-count` :
	- Renvoie le nombre de fichiers de configuration UE présents (approximation du nombre d’UE créés).

Ces endpoints représentent la partie « contrôleur custom » du workflow recommandé dans l’état de l’art ; ils pourront, dans une étape ultérieure, être appelés via des webhooks provenant d’Alertmanager ou d’un opérateur 5G.

## Fichiers importants

- `src/main.py` – application Flask qui :
	- génère la configuration UE UERANSIM,
	- crée le ConfigMap et le Pod UE,
	- crée/supprime un `Deployment` + `Service` UPF par UE.
- `scripts/demo.sh` – script simple pour exercer les flux d’ajout/suppression d’UE et vérifier les ressources UPF via `kubectl`.
- `tests/test_dynamic_upf.py` – test d’intégration de création/suppression d’UPF.

## Configuration

- L’image UPF utilisée par défaut est `free5gc/upf:latest`. Pour la changer, définir la variable d’environnement `UPF_IMAGE` avant de lancer l’application Flask.
- Le nombre de réplicas pour un Deployment UPF est contrôlable via la variable d’environnement `UPF_REPLICAS`.

## Lien avec l’état de l’art et travaux futurs

Ce POC implémente la logique minimale de slicing dynamique recommandée :

- Création d’un UPF dédié lors de la « connexion » d’un UE,
- Suppression de l’UPF lors de la « déconnexion » de l’UE.

Évolutions possibles pour se rapprocher davantage des projets de référence :

- **Intégration open5gs-operator / HEXAeBPF** : utiliser leurs CRDs pour déclarer les slices et brancher ce contrôleur sur les événements UE réels.
- **Prometheus / Alertmanager / KEDA** : exposer des métriques (UEs par slice, charge UPF) et déclencher la création/suppression ou le scaling des UPF via des webhooks et/ou des objets `ScaledObject` KEDA.
- **Opérateur Kubernetes dédié** : transformer cette app Flask en opérateur Kubernetes (par exemple avec `kopf`) pour suivre le pattern « Operator » complet.