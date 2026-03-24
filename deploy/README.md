# Graphiti REST Deploy

This folder contains the minimum handoff files for publishing and deploying the
custom Graphiti REST image that exposes native `POST /episodes`, together with
its bundled Neo4j dependency.

## Files

- `docker-compose.graphiti-rest.yml`
  - Deploys the REST service together with Neo4j
- `graphiti-rest.env.example`
  - Example environment file for the bundled deployment

## Release

Build and push a tagged image:

```bash
./scripts/build-push-graphiti-rest.sh ghcr.io/septem1997/graphiti-rest 0.28.2-episodes-v1
```

Or publish from GitHub Actions without logging into GHCR locally:

- Push this repo to GitHub
- Open `Actions`
- Run `Publish Server Image to GHCR`
- Use tag `0.28.2-episodes-v1`

## Deploy

```bash
cp deploy/graphiti-rest.env.example deploy/graphiti-rest.env
docker compose --env-file deploy/graphiti-rest.env -f deploy/docker-compose.graphiti-rest.yml up -d
```

## Smoke Check

```bash
curl -sS http://localhost:8000/healthcheck
```
