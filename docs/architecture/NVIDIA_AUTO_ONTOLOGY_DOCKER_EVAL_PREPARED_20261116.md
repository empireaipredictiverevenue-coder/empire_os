# EmpireOS — NVIDIA Auto Ontology isolated Docker deployment handoff
Date: 2026-11-16
Status: PREPARED_AND_COMPOSE_VALIDATED / NOT_STARTED

## Evidence

Founder executed the following one-time Docker smoke command on EmpireOS:

```
sudo docker run --rm --network none --read-only --cap-drop ALL \
  --security-opt no-new-privileges --user 65534:65534 \
  alpine:3.21 sh -c 'echo DOCKER_SMOKE_PASS'
```

Observed stdout ended `DOCKER_SMOKE_PASS`; Docker pulled alpine:3.21.
This verifies the Docker daemon **under founder sudo**, not daemon
permission for the remote `ubuntu` session. The remote operator still gets
`permission denied ... /var/run/docker.sock` from `docker info`.
A direct `sudo -n docker ps` remote invocation was blocked and no privilege
changes were made.

Docker Compose v5.7.1 is already installed as a checksum-verified user-scoped
CLI plugin. No need to add `ubuntu` to the docker group. Because the plugin is
only installed for ubuntu, sudo launch commands use the **absolute plugin
binary**; ordinary `sudo docker compose` might not find that user-scoped plugin.

## Prepared evaluation bundle

Path: `/srv/empire_os/runtime/nvidia_ontology_eval` (mode 0700).
This path is covered by existing EmpireOS `.gitignore` runtime rules.

- `vendor/`: copied pinned NVIDIA upstream source commit
  `3825917ac61ff3081035ae61445025f1314d157a`.
- `.env`: unique random local-only app / database secrets (0600).
  **Do not paste or commit this file.**
- `empire_graph.sqlite`: generated fixture via the verified EmpireOS
  buyer-demand graph and private HMAC shadow adapter (0600).
- `compose.yaml`: vendor-derived Docker Compose evaluation manifest (0600).

Generation and independent checks:

- `scripts/prepare_nvidia_ontology_docker_eval_20261116.py`
  (first-run-only, fails closed if staging path exists; executed as a module).
- `tests/test_nvidia_docker_eval_manifest.py`.
- `docker compose ... config -q`: PASS.
- Focused regression suite: 10 passed, including original graph adapter and
  genuine NVIDIA SQLite connector checks.

## Security properties — validated from resolved Compose

- Project name: `empire-nvidia-ontology-eval` (unique from source defaults).
- No globally fixed source `container_name` values.
- Private Docker network `sandbox` with `internal: true`.
- Only published host port: `127.0.0.1:33000 -> frontend:3000`.
- PostgreSQL, API backend and ingestion have **no published host ports**.
- pgAdmin is not an active default service (`manual` profile).
- Model endpoints are intentionally an unreachable local URL, not an API
  provider. Models and embedding are **not configured**; no inference is
  possible until a separately tested model endpoint is authorised.
- Only the generated synthetic SQLite file is mounted into ingestion/backend,
  read-only at `/reference/empire_graph.sqlite`.
- Upstream image names for backend and frontend have project-specific tags;
  the Postgres and pgAdmin data volumes remain Compose project-scoped.
- Docker services have `restart: no`; no service is activated at boot.
- Existing EmpireDB services, user accounts, migrations and workloads unchanged.

## Operator launch (one founder-controlled privileged command)

From an EmpireOS shell:

```bash
sudo /home/ubuntu/.docker/cli-plugins/docker-compose \
  -f /srv/empire_os/runtime/nvidia_ontology_eval/compose.yaml \
  --env-file /srv/empire_os/runtime/nvidia_ontology_eval/.env \
  up -d --build
```

This command is **prepared, not executed**. It will pull/build upstream
containers and start a separate local stack. It can consume CPU, RAM and disk.
It does **not** create provider billing, attach real customer databases or
publish external network services. The NVIDIA web application may be reachable
on the EmpireOS host at `http://127.0.0.1:33000`, but ontology compilation,
MCP and useful natural-language answers will remain held without model
endpoints. No customer, revenue or full runtime success is asserted.

After operator execution, inspect the actual status:

```bash
sudo /home/ubuntu/.docker/cli-plugins/docker-compose \
  -f /srv/empire_os/runtime/nvidia_ontology_eval/compose.yaml \
  --env-file /srv/empire_os/runtime/nvidia_ontology_eval/.env \
  ps
```

Runtime proof must include healthy database, migrations and frontend, plus
HTTP auth flow and independent test with MCP check_readiness.
Unsupported or failed containers should be diagnosed from logs *without*
restarting or touching unrelated production services.

## Rollback

Only after explicitly deciding to stop this named evaluation:

```bash
sudo /home/ubuntu/.docker/cli-plugins/docker-compose \
  -f /srv/empire_os/runtime/nvidia_ontology_eval/compose.yaml \
  --env-file /srv/empire_os/runtime/nvidia_ontology_eval/.env \
  down
```

No `-v`, no image prune, no force-removal of other projects. Named volumes
and the prepared fixture remain intact.
