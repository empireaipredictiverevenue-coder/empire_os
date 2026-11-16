# NVIDIA Auto Ontology — Docker execution preflight, 2026-11-16

Status: COMPOSE_INSTALLED; DOCKER_DAEMON_ACCESS_DENIED; NO CONTAINERS STARTED

## Verified on EmpireOS

- Target device: EmpireOS (Ubuntu account `ubuntu`).
- Installed official Docker Compose v5.7.1 as user-scoped CLI plugin:
  `/home/ubuntu/.docker/cli-plugins/docker-compose`.
- Download verified against NVIDIA-independent official docker/compose GitHub
  release checksum `af426722a8af5de812fcee30cc1c39f0639f5f723cbadefb25e5d4db054064cf`.
- `docker compose version`: v5.7.1 — PASS.
- Isolated smoke definition:
  `/tmp/empire-nvidia-docker-smoke-20261116/compose.yaml`.
- `docker compose -f ... config -q`: PASS.
- `docker compose -f ... up --no-build --pull never ...`:
  FAILED BEFORE CONTAINER START; `permission denied ... /var/run/docker.sock`.
- `docker ps`: identical permission denial.
- `/var/run/docker.sock`: root:docker, mode 0660.
- `getent group docker`: docker:x:109: (no direct membership for ubuntu).
- `id`: ubuntu not in docker group.
- Rootless Docker engine/tooling not found on this target.
- The alternative connected Windows device (apexengine) did not expose
  a Docker executable in the connected shell.

## Controls

- Neither the NVIDIA stack nor a smoke container was launched.
- No Docker daemon privilege was granted to any account.
- No sudo commands, systemd restarts, production database changes, network
  exposures, model-provider charges, migrations, or tenant data transfers.
- User-scoped Docker Compose installed; temporary smoke YAML remains under /tmp.
- This probe must not be reported as a running NVIDIA Auto Ontology service.

## Required next operator action

An authorised root operator must make a narrowly scoped one-time Docker
command available, or explicitly approve a persistent privileged daemon
access arrangement. Membership in the `docker` group gives root-equivalent
host control; do not change it by default.

Initial operator verification command:

```bash
sudo docker version
```

Once Docker access is authorised, run the isolated smoke before launching
the NVIDIA compose topology. NVIDIA's example compose publishes database,
backend and frontend ports on all interfaces; never deploy that default
unmodified on the production host. Its model configuration and secret
handling also require a separate, explicit evaluation release.
