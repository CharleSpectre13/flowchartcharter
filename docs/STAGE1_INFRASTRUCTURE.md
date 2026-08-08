# Stage 1 — Infrastructure Drop (v1.6.0)

## Done
- [x] Repo locked on `main`, audit green
- [x] Git tag `v1.6.0` + GitHub Release
- [x] Repository **PUBLIC**
- [x] Wheel + sdist built and attached to Release
- [x] Local verify: `pip install dist/*.whl` → engine smoke OK

## Requires secrets (operator)

### PyPI
```bash
export TWINE_USERNAME=__token__
export TWINE_PASSWORD=pypi-...   # API token
python -m build
twine upload dist/*
# or set repo secret PYPI_API_TOKEN and re-run Actions → Publish to PyPI
```

### Docker Hub
```bash
docker login
docker build -t charlespectre13/flowchart-charter-engine:1.6.0 .
docker push charlespectre13/flowchart-charter-engine:1.6.0
docker tag charlespectre13/flowchart-charter-engine:1.6.0 charlespectre13/flowchart-charter-engine:latest
docker push charlespectre13/flowchart-charter-engine:latest
```
This sandbox has no Docker daemon — run on a machine with Docker.

## Verify after publish
```bash
pip install flowchart-charter-engine==1.6.0
fcc version
docker compose up --build
```
