# Stage 1 — Infrastructure Drop & Production Armor (v1.6.1)

## Pre-flight patches (v1.6.1-Production)

| Vulnerability | Fix |
|---------------|-----|
| Ephemeral state amnesia | `StatePersister` → `data/system_state.json` after every workload / sync; restore on FastAPI lifespan boot |
| Unsecured `/system/*` | `X-API-Key` header via `FCC_ADMIN_KEY` (`security.require_admin_key`) |

### Environment

```bash
export FCC_ADMIN_KEY="replace-with-long-random-secret"
export FCC_STATE_PATH="/app/data/system_state.json"   # optional override
export FCC_DATA_DIR="/app/data"
# Local demos only (never production):
# export FCC_ADMIN_OPEN=1
```

### Admin calls

```bash
curl -X POST http://127.0.0.1:8090/system/trigger-monday-sync \
  -H "X-API-Key: $FCC_ADMIN_KEY"

curl -X POST http://127.0.0.1:8090/system/load-playbook \
  -H "X-API-Key: $FCC_ADMIN_KEY" \
  -F file=@library/secops_vulnerability_audit.yaml
```

Workload ingestion remains open: `POST /workload/submit` (no admin key).

---

## GitHub Secrets (PyPI + Docker)

### 1. PyPI Trusted Publishing / token

1. Create a PyPI account → Account settings → API tokens → scope `flowchart-charter-engine`.
2. GitHub repo → **Settings → Secrets and variables → Actions**
3. New repository secret:
   - Name: `PYPI_API_TOKEN`
   - Value: `pypi-AgEIcHlwaS5vcmc...` (full token)

Workflow: `.github/workflows/publish.yml` runs on release publish.

Manual fallback:
```bash
python -m build
export TWINE_USERNAME=__token__
export TWINE_PASSWORD="$PYPI_API_TOKEN"
twine upload dist/*
```

### 2. Docker Hub

1. Docker Hub → Account Settings → Security → New Access Token
2. GitHub secrets:
   - `DOCKERHUB_USERNAME`
   - `DOCKERHUB_TOKEN`

Local publish:
```bash
docker login -u "$DOCKERHUB_USERNAME" -p "$DOCKERHUB_TOKEN"
docker build -t "$DOCKERHUB_USERNAME/flowchart-charter-engine:1.6.1" .
docker push "$DOCKERHUB_USERNAME/flowchart-charter-engine:1.6.1"
docker tag "$DOCKERHUB_USERNAME/flowchart-charter-engine:1.6.1" \
           "$DOCKERHUB_USERNAME/flowchart-charter-engine:latest"
docker push "$DOCKERHUB_USERNAME/flowchart-charter-engine:latest"
```

Compose (enterprise stack):
```bash
export FCC_ADMIN_KEY="..."
docker compose up --build
# API :8090  ·  Qdrant :6333  ·  state volume engine_data
```

Ensure compose mounts a volume on `/app/data` so `system_state.json` survives restarts
(already mapped as `engine_data:/app/data` in `docker-compose.yml`).

---

## Final deployment checklist

```bash
# 1. Tag + release
git tag -a v1.6.1 -m "v1.6.1-Production pre-flight armor"
git push origin v1.6.1
gh release create v1.6.1 --title "v1.6.1-Production" --generate-notes

# 2. Verify public install
pip install flowchart-charter-engine==1.6.1
# or from release asset:
# pip install https://github.com/CharleSpectre13/flowchartcharter/releases/download/v1.6.1/flowchart_charter_engine-1.6.1-py3-none-any.whl

# 3. Boot
export FCC_ADMIN_KEY="$(openssl rand -hex 24)"
export FCC_STATE_PATH=./data/system_state.json
python -m flowchartcharter

# 4. Prove persistence
curl -X POST localhost:8090/workload/submit -H 'Content-Type: application/json' \
  -d '{"workload":"Legacy Code Refactor"}'
# restart process → days_ready and fear indices rehydrate from data/system_state.json
```

## Release assets

| Artifact | Purpose |
|----------|---------|
| `flowchart_charter_engine-1.6.1-py3-none-any.whl` | pip install |
| `flowchart_charter_engine-1.6.1.tar.gz` | sdist |
| Docker image `:1.6.1` | enterprise compose |
