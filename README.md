# Multi-Tenant SaaS API

API multi-tenant sécurisée pour la recherche documentaire, construite avec FastAPI et Streamlit.

---

## 📋 Table des matières

1. [Explication de l'approche](#-explication-de-lapproche)
2. [Lancer le Backend](#-lancer-le-backend)
3. [Lancer l'Interface](#-lancer-linterface)
4. [Tester le Client A et Client B](#-tester-le-client-a-et-client-b)
5. [Structure du projet](#-structure-du-projet)
6. [Architecture](#-architecture)
7. [Endpoints API](#-endpoints-api)

---

## 🧠 Explication de l'approche

### Objectif

Construire une API SaaS multi-tenant où **deux clients (Tenant A et Tenant B)** utilisent le même système mais avec une **isolation stricte des données**.

### Principes de sécurité multi-tenant

| Principe                     | Implémentation                                                 |
| ---------------------------- | -------------------------------------------------------------- |
| **Identification du tenant** | Via header HTTP `X-API-KEY` (jamais dans le body ou query)     |
| **Résolution côté serveur**  | Le tenant est résolu par le middleware, pas par le client      |
| **Isolation des données**    | Chaque requête n'accède qu'aux documents du tenant authentifié |
| **Pas de fuite de données**  | Tenant A ne peut JAMAIS accéder aux données de Tenant B        |

### Flux de sécurité

```
1. Client envoie requête avec header X-API-KEY
2. Middleware intercepte et valide la clé API
3. Middleware résout l'identité du tenant (serveur-side)
4. TenantContext attaché à request.state
5. Route handler accède UNIQUEMENT aux données du tenant
6. Si clé invalide → 401 Unauthorized
```

### Choix techniques

- **FastAPI** : Framework moderne, typage fort, documentation auto-générée
- **Middleware** : Interception centralisée pour validation systématique
- **Pydantic** : Validation des données entrantes/sortantes
- **Stockage en mémoire** : Simple et efficace pour ce MVP (extensible vers SQLite/PostgreSQL)
- **Recherche par mots-clés** : Insensible aux accents pour le français

---

## 🚀 Lancer le Backend

### Prérequis

```bash
Python 3.10+
```

### Installation des dépendances

```bash
pip install -r requirements.txt
```

Ou manuellement :

```bash
pip install fastapi uvicorn pydantic streamlit requests
```

### Démarrer le serveur FastAPI

```bash
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Vérifier que le backend fonctionne

- **API** : http://localhost:8000
- **Documentation Swagger** : http://localhost:8000/docs
- **Health Check** : http://localhost:8000/health

---

## 🖥️ Lancer l'Interface

### Démarrer Streamlit (dans un nouveau terminal)

```bash
streamlit run app.py
```

L'interface s'ouvre automatiquement sur : http://localhost:8501

### Utilisation de l'interface

1. **Sidebar** : Sélectionner le tenant (Tenant A ou Tenant B)
2. **Zone de texte** : Entrer votre question
3. **Bouton** : Cliquer sur "Get Answer"
4. **Résultat** : Voir la réponse + document source + nom du tenant

---

## 🧪 Tester le Client A et Client B

### Clés API

| Client       | Clé API       |
| ------------ | ------------- |
| **Tenant A** | `tenantA_key` |
| **Tenant B** | `tenantB_key` |

### Test 1 : Tenant A accède à ses documents

```bash
curl -X POST "http://localhost:8000/ask" \
  -H "X-API-KEY: tenantA_key" \
  -H "Content-Type: application/json" \
  -d "{\"question\": \"procedure resiliation\"}"
```

**Résultat attendu** :

```json
{
  "answer": "Procédure résiliation. La résiliation doit être enregistrée dans le CRM.",
  "source": "docA1_procedure_resiliation.txt",
  "tenant": "Tenant A"
}
```

### Test 2 : Tenant B accède à ses documents

```bash
curl -X POST "http://localhost:8000/ask" \
  -H "X-API-KEY: tenantB_key" \
  -H "Content-Type: application/json" \
  -d "{\"question\": \"procedure sinistre\"}"
```

**Résultat attendu** :

```json
{
  "answer": "Procédure sinistre. Tout sinistre doit être déclaré dans les 5 jours ouvrés.",
  "source": "docB1_procedure_sinistre.txt",
  "tenant": "Tenant B"
}
```

### Test 3 : Isolation des données (CRITIQUE)

Tenant B essaie d'accéder aux données de Tenant A :

```bash
curl -X POST "http://localhost:8000/ask" \
  -H "X-API-KEY: tenantB_key" \
  -H "Content-Type: application/json" \
  -d "{\"question\": \"procedure resiliation\"}"
```

**Résultat attendu** : Tenant B ne reçoit PAS les données de Tenant A !

```json
{
  "answer": "Procédure sinistre.",
  "source": "docB1_procedure_sinistre.txt",
  "tenant": "Tenant B"
}
```

(Retourne uniquement ses propres documents, pas ceux de Tenant A)

### Test 4 : Clé API invalide

```bash
curl -X POST "http://localhost:8000/ask" \
  -H "X-API-KEY: invalid_key" \
  -H "Content-Type: application/json" \
  -d "{\"question\": \"test\"}"
```

**Résultat attendu** : 401 Unauthorized

```json
{
  "detail": "Invalid API key",
  "error": "unauthorized"
}
```

### Test 5 : Clé API manquante

```bash
curl -X POST "http://localhost:8000/ask" \
  -H "Content-Type: application/json" \
  -d "{\"question\": \"test\"}"
```

**Résultat attendu** : 401 Unauthorized

```json
{
  "detail": "Missing X-API-KEY header",
  "error": "unauthorized"
}
```

### Tests via PowerShell (Windows)

```powershell
# Tenant A
Invoke-RestMethod -Uri "http://localhost:8000/ask" -Method Post -Headers @{"X-API-KEY"="tenantA_key"; "Content-Type"="application/json"} -Body '{"question": "procedure resiliation"}'

# Tenant B
Invoke-RestMethod -Uri "http://localhost:8000/ask" -Method Post -Headers @{"X-API-KEY"="tenantB_key"; "Content-Type"="application/json"} -Body '{"question": "procedure sinistre"}'
```

---

## 📁 Structure du projet

```
RAG_MVP_ACTUDATA/
├── main.py                       # Backend FastAPI complet (multi-tenant)
├── app.py                        # Frontend Streamlit
├── requirements.txt              # Dépendances Python
├── README.md                     # Ce fichier
├── tenant_files/                 # Stockage des documents par tenant
│   ├── tenanta/                 # Documents de Tenant A
│   │   ├── docA1_procedure_resiliation.txt
│   │   └── docA2_produit_rc_pro_a.txt
│   └── tenantb/                 # Documents de Tenant B
│       ├── docB1_procedure_sinistre.txt
│       └── docB2_produit_rc_pro_b.txt
├── auth.py                       # (Legacy)
├── models.py                     # (Legacy)
├── rag.py                        # (Legacy)
├── vectorstore.py                # (Legacy)
└── data/                         # Index FAISS (Legacy)
```

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      Streamlit Frontend                          │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │  - Saisie de la clé API (sidebar)                           ││
│  │  - Saisie de la question                                    ││
│  │  - Affichage réponse + source                               ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ HTTP POST /ask
                              │ Header: X-API-KEY
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      FastAPI Backend                             │
├─────────────────────────────────────────────────────────────────┤
│  MIDDLEWARE (TenantMiddleware)                                   │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ 1. Extraire X-API-KEY des headers                           ││
│  │ 2. Valider contre le mapping serveur                        ││
│  │ 3. Résoudre l'identité du tenant                            ││
│  │ 4. Attacher TenantContext à request.state                   ││
│  │ 5. Rejeter si non autorisé (401)                            ││
│  └─────────────────────────────────────────────────────────────┘│
├─────────────────────────────────────────────────────────────────┤
│  ROUTES (routes.py)                                              │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ POST /ask       → Répondre aux questions (isolé)            ││
│  │ GET /health     → Vérification de santé                     ││
│  │ GET /documents  → Lister les documents du tenant            ││
│  │ GET /tenant/info→ Info sur le tenant                        ││
│  └─────────────────────────────────────────────────────────────┘│
├─────────────────────────────────────────────────────────────────┤
│  COUCHE DONNÉES (Isolée par tenant)                              │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ data_loader.py → Charge docs depuis dossiers tenant         ││
│  │ search.py      → Recherche UNIQUEMENT dans docs du tenant   ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

---

## 📡 Endpoints API

### POST /ask

Répondre à une question en utilisant les documents du tenant.

**Headers requis** :

- `X-API-KEY` : Clé API du tenant

**Body** :

```json
{
  "question": "Votre question ici"
}
```

**Réponse** :

```json
{
  "answer": "Réponse extraite des documents",
  "source": "nom_du_document.txt",
  "tenant": "Tenant A"
}
```

### GET /health

Vérification de santé (pas d'authentification requise).

### GET /documents

Liste tous les documents du tenant authentifié.

### GET /tenant/info

Informations sur le tenant authentifié.

---

## 🛡️ Garanties de sécurité

| Menace               | Protection                                    |
| -------------------- | --------------------------------------------- |
| Usurpation via body  | ❌ Tenant JAMAIS lu depuis le body            |
| Usurpation via query | ❌ Tenant JAMAIS lu depuis les paramètres     |
| Accès cross-tenant   | ✅ Toutes les requêtes filtrées par tenant_id |
| Clé API invalide     | ✅ Retourne 401 Unauthorized                  |
| Clé API manquante    | ✅ Retourne 401 Unauthorized                  |

---

## 📦 Dépendances

- **FastAPI** : Framework web
- **Uvicorn** : Serveur ASGI
- **Pydantic** : Validation des données
- **Streamlit** : Interface utilisateur
- **Requests** : Client HTTP
