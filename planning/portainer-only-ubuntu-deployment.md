# Plan: Portainer-Only Ubuntu Deployment

## Overview

Replace the Ubuntu release path's SSH, `rsync`, remote-file, and remote-Docker
dependencies with authenticated Portainer stack/API operations. A normal release
will build and push immutable images, instruct Portainer to deploy or update the
production/staging stack, and verify the result over HTTPS. Portainer is the
deployment control plane; the Docker host is not accessed by a release command.

This is feasible for application deployment. It cannot eliminate the need for a
separate recovery path: Portainer cannot install, start, or repair itself, Docker,
the host firewall, or DNS while it is unavailable. The supported replacement is
a documented, tested local-console/provider-console break-glass procedure. SSH
will not be used by the repository's deploy tooling or required for normal
operation.

## Scope

- Goal: `ubuntu_deploy.py` deploys, stages, promotes, and rolls back Ubuntu
  workloads through Portainer HTTPS APIs only; no supported release operation
  invokes `ssh`, `rsync`, or a remote shell.
- Goal: Portainer can pull private GHCR images using its own least-privileged
  registry credential. Runtime configuration currently held in `.env` and
  `.env.secrets` reaches containers as explicit Portainer stack environment
  variables, never as files synchronized to the Ubuntu host.

- Goal: the Caddy platform is declarative and updatable through Portainer rather
  than by modifying a host-mounted Caddyfile over SSH.
- Non-goals: automate first installation of Docker or Portainer, remove the
  operating system's emergency-console access, or modify unrelated Azure
  deployment behavior.
- Non-goals: silently preserve the legacy remote-Compose fallback. A failed
  Portainer preflight must fail safely and direct the operator to the break-glass
  procedure.
- Affected areas: `scripts/deploy/ubuntu_deploy.py`,
  `scripts/deploy/portainer_helpers.py`, `scripts/deploy/env_schema.py`,
  `docker/docker-compose*.yml`, `docker/proxy/`, deploy tests, environment
  examples, `README.md`, and `docs/deploy/`.

## Current Context

- The repository already defaults `UBUNTU_NO_SSH=true` and creates application
  stacks with Portainer's standalone-string API. Focused unit coverage proves
  that path does not execute `ssh` or `rsync`.
- The same deploy script retains an SSH branch for remote directory creation,
  source/environment transfer, Portainer bootstrap, GHCR login/pull, Caddy
  refresh, Caddy route registration, and a direct-Docker-Compose fallback.
- `docker/ubuntu_start.sh` sources host-mounted `.env` and `.env.secrets`, and
  `docker/docker-compose.ubuntu.yml` bind-mounts that host directory. In
  SSH-free mode those files are not transferred, so this is not a deployable
  Portainer-only configuration.
- GitHub Environment secrets can remain the CI source for the full runtime
  files: `RUNTIME_ENV_DOTENV` supplies `.env` and
  `RUNTIME_SECRETS_DOTENV` supplies `.env.secrets`. GitHub does not expose
  either secret directly to Portainer. The GitHub Actions runner must validate
  the content in its temporary directory, map the allowed keys to stack
  environment entries, then send those entries through the authenticated
  Portainer stack API. The container receives ordinary process environment
  variables and no longer sources either file.

- The current Caddy flow depends on a bind-mounted Caddyfile, host-side route
  merging, and remote restarts. It must be replaced rather than merely skipped.
- The stack payload currently provides `Env: []` and no Portainer registry ID.
  Private GHCR images therefore depend on an SSH `docker login`/`docker pull`.
- Portainer's documented standalone-stack API supports inline Compose content,
  stack environment entries, registry IDs, and webhooks. Its documented GitOps
  stack support can poll or be webhook-triggered, but Git deployment with
  relative host-path volumes is edition-dependent. This plan deliberately uses
  image-only, inline stack payloads for the workload and a custom Caddy image,
  so it does not depend on that edition-specific feature.

## Architecture Decisions

1. **Use Portainer's authenticated stack API as the deployment contract.**
   `ubuntu_deploy.py` remains the local release orchestrator: it builds/pushes
   immutable application, storage-manager, and proxy images, then calls
   Portainer. It never opens a remote shell. Webhooks may remain an optional
   trigger, but access-token API operations are required for deploy, staging,
   promotion, preflight, and verification.
2. **GitHub Environment secrets supply CI runtime inputs; Portainer owns their
   deployed form.** The release workflow reads `RUNTIME_ENV_DOTENV` and
   `RUNTIME_SECRETS_DOTENV` only into `$RUNNER_TEMP` (or parses them in memory),
   applies the runtime schema, and converts the permitted keys into explicit
   Portainer `Env` entries. Compose maps those entries explicitly into the app,
   storage-manager, and Caddy services. The image receives process environment
   variables and must not source host files. Local operator deployment accepts
   explicit runtime-file inputs under the same schema but never transfers them
   to the host. A named Docker volume replaces the application workspace bind
   mount, preserving data without requiring a remote directory.
3. **Portainer owns private-image pulls.** Configure a dedicated GHCR
   `read:packages` credential once in Portainer and reference only its numeric
   registry ID from deployment configuration. Do not copy the CI/write token to
   the Ubuntu host or include it in a stack payload.
4. **Caddy becomes an image-based Portainer platform stack.** Build a small
   Caddy image that contains the reviewed Caddyfile and consumes only explicit
   stack variables. The Caddy stack owns the named `caddy` network and durable
   certificate/config volumes; workload stacks join that network as external.
   The stock app and Portainer routes are declarative in the Caddy image, so
   application deployment never edits Caddy configuration dynamically.
5. **Keep Portainer itself outside its own update path.** The migration may
   connect the existing Portainer container to the Caddy network through the
   Portainer Docker proxy/API, but releases must not delete/recreate Portainer.
   Pin its version and document console-only recovery/update instructions.
6. **Use an immutable image reference per release.** A tag containing the git
   SHA (or a digest) is passed to the stack. This makes staging, promotion, and
   rollback deterministic and removes reliance on SSH pre-pulls or mutable
   `latest` tags.

## Non-SSH Deployment Constraints

### Runtime `.env` and `.env.secrets` flow

The files remain a source-format convenience, not a deployed artifact:

```text
GitHub Environment secrets (or explicit local files)
  -> temporary runner-only validation against RUNTIME_SCHEMA
  -> approved key-to-service mapping and Portainer stack Env payload
  -> Portainer stack metadata / Docker Compose interpolation
  -> environment of the running container process
```

The implementation must define a strict dataclass-backed mapping of every
permitted runtime key to the service(s) that need it. For example, `APP_VERSION`
is passed to the application, `SM_*` values to `storage-manager`, and
`BASIC_AUTH_USER`/`BASIC_AUTH_HASH` to Caddy. An `APP_SECRET` is only passed to
the app if that runtime actually consumes it. Unknown keys and missing required
service mappings fail before contacting Portainer. The runner deletes temporary
files even on failure and never writes them under the repository or to the
Ubuntu host.

GitHub Actions secrets are limited to 48 KB each. Phase 1 must measure the two
source files before adoption and fail with a safe migration instruction if either
exceeds that limit. Because the source files are structured, GitHub's automatic
masking may not reliably redact derived individual values; the workflow must
avoid shell tracing/output altogether and explicitly mask any value it passes to
another process.

### Security and operational limits

- Portainer receives the stack environment values and persists deployment
  metadata. Those values are therefore visible to Portainer administrators and
  potentially to host/Docker administrators. GitHub secret masking does not
  apply after the API call. This is acceptable only if Portainer is treated as a
  protected secret-bearing control plane; otherwise a dedicated external secret
  provider must be adopted before this migration.
- A Portainer API token is highly privileged: it can create workloads with
  Docker-host access. It requires least-privilege scope where supported, a
  dedicated automation identity, TLS-only access, protected GitHub Environment
  secrets, rotation, and redacted logs.
- No arbitrary files can be copied during a release. Configuration must be an
  explicit environment value, immutable image content, or intentional named
  volume data. Ad-hoc certificates, Caddyfile edits, and local project files
  cannot be deployed as hidden side effects.
- Portainer cannot bootstrap or repair Docker, itself, the host firewall, DNS,
  or a failed Caddy control plane. The local/provider console recovery runbook
  remains mandatory. SSH may be disabled after cutover, but there must be a
  tested non-SSH recovery path first.
- Dynamic registration of arbitrary shared Caddy routes is removed. New routes
  are reviewed changes to the declarative platform Caddy stack, then deployed
  through Portainer.

### External Secret Provider Options and Bootstrap Identity

Every runtime secret-provider design has a trust anchor. Removing SSH removes
the remote transport, not that trust-anchor requirement. The approved choices
are deliberately different in cost and scope:

| Option | How the container authenticates | Secret in the application container | Fit for Portainer-managed standalone Ubuntu |
| --- | --- | --- | --- |
| **Portainer stack environment (default)** | It does not call an external provider; Portainer supplies the approved values at deploy time. | No provider credential; the runtime values are environment variables. | Yes. Requires accepting Portainer as a secret-bearing control plane. |
| **Azure Key Vault with service principal** | Client secret or certificate is supplied by Portainer and exchanged for an Entra token. | Yes—one bootstrap credential or certificate. | Technically possible, but does not improve the bootstrap-secret problem; do not choose by default. |
| **Azure Arc server managed identity** | The Arc agent provides a host system-assigned identity that can request an Entra token for Key Vault. | No long-lived Entra credential, but a container needs a tightly controlled path to the host agent/token endpoint. | Possible only after a security design and proof-of-access test. The Arc agent is host infrastructure, not a Portainer stack feature. |
| **Move the workload to Azure Container Apps, ACI, or AKS** | The Azure hosting platform supplies a managed/workload identity. | No long-lived Entra credential. | Not a Portainer-on-Ubuntu solution; it is an intentional platform migration outside this plan's scope. |
| **SPIFFE/Vault-style identity broker** | A host or cluster agent attests the workload and issues short-lived credentials. | No long-lived provider credential, but the agent/socket is a privileged host trust anchor. | Feasible but materially expands the platform; not a default alternative. |

On a standalone Ubuntu Docker host, Azure managed identity is not automatically
available to containers. Azure Arc-enabled servers can have a system-assigned
identity, but Microsoft documents the identity endpoint for processes running on
the server and treats the server as its security boundary. The implementation
must not expose that endpoint, its challenge material, host networking, or a
privileged socket directly to every application container. If this option is
selected, introduce one narrowly scoped, independently reviewed broker and
prove that it grants only the Key Vault access required by the intended
workload.

### Decision Gate

Phase 2 must not begin until the operators choose one of the documented trust
models. The default is Portainer stack environment values. If operators cannot
accept that Portainer holds a deployed copy of the runtime values, stop this
migration at Phase 1 and choose either a separately scoped Azure platform
migration or an Azure Arc/broker design. A service-principal credential stored
in Portainer is not an acceptable substitute unless its residual exposure is
explicitly accepted. Do not conceal a bootstrap credential in a host bind mount
or a Git repository as a workaround.

## Task Overview

- [ ] Phase 0: Cleanup and documentation audit
- [ ] Phase 1: Portainer capability and recovery preflight
- [ ] Phase 2: Make Compose and images host-file independent
- [ ] Phase 3: Replace the deploy engine with Portainer-only operations
- [ ] Phase 4: Migrate the live control plane and validate releases
- [ ] Phase 5: Remove SSH artifacts and complete documentation handoff

## Phase 0 - Cleanup and Documentation Audit

Follow `.github/skills/code-cleanup/SKILL.md` for the deployment module. Read
`.github/skills/code-simplify/SKILL.md` and
`.github/skills/typed-code-generation/SKILL.md` before changing Python code.

### Tasks

- [ ] Inventory every executable SSH/`rsync` caller and every setting that
  supports it, including the proxy deploy script, Caddy registration module,
  remote-Compose fallback, `install_ssh_public_key.sh`, and their tests.
- [ ] Map the host-path dependencies in both Compose files and the proxy stack;
  distinguish persistent data that needs a named volume from configuration that
  needs an explicit Portainer stack variable.
- [ ] Inventory every key in `RUNTIME_SCHEMA`, identify its consuming
  service(s), and decide whether it is deployable runtime configuration,
  build-only configuration, or obsolete. Record the mapping without reading or
  printing real secret files.
- [ ] Audit `README.md` and `docs/deploy/` for conflicting SSH-free claims,
  duplicated Caddy instructions, stale remote-directory guidance, and broken
  links. Record the canonical post-migration runbook locations.
- [ ] Capture a clean baseline using the existing focused deployment tests.

### Acceptance Criteria

- [ ] The removal list and every needed compatibility migration are explicit;
  no SSH-only behavior is left implicit in a fallback or hook.
- [ ] The runtime configuration mapping contains no real secret values.
- [ ] Every runtime-schema key has an explicit disposition; no existing
  container depends on an implicit host-file lookup.
- [ ] Documentation has one identified owner for deployment and one for
  break-glass recovery.

### Verification

- [ ] `source .venv/bin/activate && python -m pytest tests/pytests/test_ubuntu_deploy.py tests/pytests/test_caddy_register.py tests/pytests/test_env_schema.py -v`
- [ ] `rg -n -i '\\bssh\\b|\\brsync\\b|UBUNTU_SSH|REMOTE_DIR|SYNC_SECRETS' scripts docker docs README.md env.deploy.example`

### Exit Criteria

- [ ] A reviewable removal/migration checklist exists before code behavior is
  changed.

## Phase 1 - Portainer Capability and Recovery Preflight

### Tasks

- [ ] Add a read-only Portainer preflight (or a `--check` mode) that validates
  TLS, the Portainer version/edition, the access token, endpoint ID, endpoint
  type, required stack permissions, current stack ownership, the `caddy`
  network, and the existing Portainer/Caddy containers. Redact every token and
  response field that can contain credentials.
- [ ] Confirm the target version's OpenAPI contract for standalone stack
  create/update, stack environment variables, registry IDs, webhook creation,
  network/container inspection, and container lifecycle operations. Use the
  Portainer server's version-specific API documentation, not assumed field
  names.
- [ ] Define the typed runtime-environment boundary: parse the GitHub-provided
  `.env` and `.env.secrets` source content at the runner, validate against
  `RUNTIME_SCHEMA`, normalize it into explicit service environment models, and
  serialize only the approved values into Portainer `Env` entries. Define the
  equivalent explicit local-file interface for a manual release.
- [ ] Add a protected GitHub Environment configuration for the Portainer
  release. Reuse `RUNTIME_ENV_DOTENV` and `RUNTIME_SECRETS_DOTENV`, add a
  dedicated `PORTAINER_ACCESS_TOKEN`, and keep the GHCR write token separate
  from the Portainer-owned GHCR read credential.
- [ ] Record the selected runtime-secret trust model. If it is not the default
  Portainer stack environment model, produce a separate threat model for the
  runtime identity path, prove the container can request only a short-lived
  token without privileged host access, and obtain review before Phase 2.
- [ ] In Portainer, create a distinct GHCR registry credential with only
  `read:packages`, record its registry ID as non-secret configuration, and
  prove it can pull the candidate image without a host `docker login`.
- [ ] Write the console-only break-glass runbook: host prerequisites, how to
  restore the pinned Portainer container and its data volume, how to restore
  Caddy networking/cert volumes, and the criteria for disabling/removing SSH
  from the normal operator workflow.

### Acceptance Criteria

- [ ] Preflight makes no Docker or stack mutations and reports an actionable
  failure for missing Portainer capability, authorization, registry, network,
  or TLS prerequisites.
- [ ] The chosen Portainer API contract is pinned to the observed deployment
  target version and covered by request-shape tests.
- [ ] The Portainer-owned GHCR credential cannot push packages and appears only
  in Portainer's registry configuration—not in the CI configuration, local
  deploy files, logs, or stack environment values.
- [ ] CI accesses the runtime secrets only after environment protection rules
  approve the release job, uses `$RUNNER_TEMP` with restrictive permissions when
  a file is necessary, and removes the temporary files on every exit path.
- [ ] A Portainer outage has a tested recovery procedure that does not depend
  on the repository deploy command.

### Verification

- [ ] Focused fake-HTTP tests cover a valid preflight, unauthorized token,
  missing registry, wrong endpoint type, and non-destructive behavior.
- [ ] Run the preflight against the local-network Portainer endpoint and save
  only redacted output under `out/` for review.
- [ ] Review the current Portainer API specification:
  [Portainer CE API docs](https://api-docs.portainer.io/?edition=ce&version=2.39.0)
  and [Portainer stack API reference](https://github.com/portainer/portainer-skills/blob/main/portainer-api/references/stacks.md).

### Files Likely Touched

- `scripts/deploy/portainer_helpers.py`
- `scripts/deploy/ubuntu_deploy.py`
- `scripts/deploy/env_schema.py`
- `tests/pytests/test_ubuntu_deploy.py`
- `.github/workflows/deploy.yml`
- `docs/deploy/UBUNTU_SERVER.md`

### Exit Criteria

- [ ] A real target passes the read-only preflight and the API contract is
  confirmed for that target.

## Phase 2 - Make Compose and Images Host-File Independent

### Tasks

- [ ] Write failing Compose/rendering tests that prove an Ubuntu workload stack
  has no `ENV_DIR` bind mount, no runtime `env_file`, no absolute local path,
  no build context at the Portainer API boundary, and a named persistent
  workspace volume. Add tests proving the approved runtime stack variables map
  to their intended service and no other service receives a secret by default.
- [ ] Refactor `docker/ubuntu_start.sh` and
  `docker/docker-compose.ubuntu.yml` so the app receives explicit container
  environment values and no longer sources host `.env` or `.env.secrets`
  files. Preserve the log-volume and storage-manager behavior.
- [ ] Introduce a reviewed, image-based Caddy build under `docker/proxy/` that
  copies the Caddyfile into the image. Replace proxy `env_file` and Caddyfile
  host bind mounts with explicit Portainer stack variables and named volumes.
  Parameterize the Portainer hostname rather than retaining a real domain in a
  tracked Caddyfile.
- [ ] Define a platform Caddy Compose stack that creates a stable named `caddy`
  network and has no external host-directory dependencies. Keep workload stacks
  image-only and attach them to that network.
- [ ] Update image build/push logic to publish a pinned proxy image alongside
  the app and storage-manager images, and pass immutable references into
  Portainer stack rendering.

### Acceptance Criteria

- [ ] Portainer can deploy the fully rendered workload and platform Caddy stack
  on a clean Docker endpoint without files copied to the host.
- [ ] The application workspace, logs, Caddy data, and Caddy config have
  intentional named-volume lifecycles and are not removed during routine stack
  updates.
- [ ] Caddy continues to enforce TLS and Basic Auth, with its actual credential
  values supplied only through Portainer's protected stack configuration.
- [ ] The deployed app receives the same supported runtime settings from its
  process environment as it previously received from the two host files, with
  no secret value emitted in test failures or logs.
- [ ] The tracked Caddy configuration contains no environment-specific host or
  credential.

### Verification

- [ ] Focused tests for stack rendering, image build commands, Caddy Compose
  contract, and volume/network declarations.
- [ ] `docker compose -f docker/docker-compose.yml -f docker/docker-compose.ubuntu.yml config` with safe test-only environment values.
- [ ] Build the proxy image locally, then run `caddy validate` against the
  embedded configuration using safe test-only variables.

### Files Likely Touched

- `docker/ubuntu_start.sh`
- `docker/docker-compose.yml`
- `docker/docker-compose.ubuntu.yml`
- `docker/proxy/Dockerfile`
- `docker/proxy/docker-compose.yml`
- `docker/proxy/Caddyfile`
- `scripts/deploy/ubuntu_deploy.py`
- `tests/pytests/test_ubuntu_deploy.py`

### Exit Criteria

- [ ] The rendered Portainer payload is portable to a host with no checked-out
  repository and no copied environment files.

## Phase 3 - Replace the Deploy Engine with Portainer-Only Operations

### Tasks

- [ ] Following the bug-fix workflow for each removal regression, first add
  failing tests that require the normal deploy path to make zero `ssh`, `rsync`,
  or remote-Compose calls and to fail rather than fall back when Portainer is
  unavailable or uninitialized.
- [ ] Replace the delete/create-with-empty-environment implementation with a
  typed Portainer stack client that resolves an existing stack, performs the
  version-appropriate create/update operation, passes explicit `Env` entries
  and `Registries`, and waits for observable container/health readiness. Read
  and follow `.github/skills/typed-code-generation/SKILL.md` before modifying
  this Python production or test code.
- [ ] Remove the `--host`, `--no-ssh`, `--remote-dir`, `--sync-secrets`, and
  SSH-only fallback semantics from `ubuntu_deploy.py`. Retain only Portainer
  endpoint, API host, stack name, registry ID, staging name, and safe
  image/version inputs.
- [ ] Move platform Caddy deployment to an explicit Portainer operation, not a
  side effect of every workload release. A routine application deploy must only
  verify its expected Caddy route/network; route changes require a reviewed
  platform-stack update.
- [ ] Keep staging/swap entirely within Portainer: deploy a distinct staging
  stack with collision-free container names, verify it is healthy, promote the
  immutable image to production, and stop staging through the Docker proxy API.
- [ ] Ensure errors are generic to the user while deployment logs identify the
  safe corrective action; never include HTTP authorization headers, webhook
  tokens, registry credentials, or full Portainer API bodies.

### Acceptance Criteria

- [ ] Every routine deploy mode (candidate, production, swap, rollback) is
  executable with an absent SSH binary and without an `UBUNTU_SSH_HOST` value.
- [ ] A Portainer error leaves an existing production stack untouched unless a
  deliberate, verified update has begun; there is no silent direct-Docker
  fallback.
- [ ] Staging and production share no explicit container name and only the
  intended production route receives public traffic.
- [ ] The stack API payload uses a configured registry ID for every private
  image and contains only approved explicit environment keys.

### Verification

- [ ] Unit tests use a fake Portainer server to assert create, update, registry,
  staging, rollback, timeout, 401, 409, and 5xx behavior.
- [ ] A test invokes the deploy script with `PATH` lacking SSH/rsync and asserts
  the entire normal path completes against the fake API.
- [ ] A workflow-level test or review fixture proves that multiline GitHub
  secret values are passed through standard input/environment handling, not as
  command-line arguments, and are not echoed by shell tracing.
- [ ] `source .venv/bin/activate && python -m pytest tests/pytests/test_ubuntu_deploy.py tests/pytests/test_env_schema.py -v`

### Files Likely Touched

- `scripts/deploy/ubuntu_deploy.py`
- `scripts/deploy/portainer_helpers.py`
- `scripts/deploy/env_schema.py`
- `scripts/deploy/deploy_hooks.py`
- `tests/pytests/test_ubuntu_deploy.py`
- `tests/pytests/test_deploy_hooks_unit.py`

### Exit Criteria

- [ ] The deploy engine has no executable SSH/rsync/direct-Compose branch and
  all focused tests pass.

## Phase 4 - Migrate the Live Control Plane and Validate Releases

### Tasks

- [ ] Schedule a maintenance window and make rollback records: exported
  redacted Portainer stack definitions, container/image identifiers, Caddy
  certificate/config volume names, and known-good immutable image digests.
- [ ] Use Portainer to deploy the platform Caddy stack, preserving its named
  certificate/config volumes and the existing `central-proxy` ownership/name.
  Connect the existing Portainer container to the `caddy` network through the
  Portainer Docker proxy/API if required. Do not recreate Portainer.
- [ ] Deploy an isolated candidate application stack using the new path, prove
  Portainer pulls the private image, confirm its volumes/networks, and inspect
  redacted container logs for the absence of missing-host-env behavior.
- [ ] Promote the candidate, verify the public Caddy route, authentication,
  health endpoint, Portainer API route, storage-manager behavior, and staging
  stop behavior. Roll back to the recorded immutable image if any check fails.
- [ ] Reboot-test the host in a planned window and prove Portainer, Caddy,
  volumes, network, and the production stack recover without a release script
  or SSH action.

### Acceptance Criteria

- [ ] Application deployment and promotion complete using only HTTPS access to
  Portainer.
- [ ] A restart of the Docker host preserves the control plane, workloads,
  workspace/log data, and public routing.
- [ ] Rollback works from an immutable image reference and does not require a
  host directory or Docker login.

### Verification

- [ ] Portainer UI/API shows the expected stacks, images, registry association,
  named volumes, and `caddy` network.
- [ ] Browser/curl checks confirm unauthenticated app requests remain blocked,
  authenticated app access works, and `https://portainer.<domain>` remains
  reachable through Caddy.
- [ ] Deploy a fresh image twice: once to staging and once by promotion; verify
  the image digest and version-log rows match the intended release.

### Exit Criteria

- [ ] One end-to-end candidate-to-production deployment and one recovery test
  have succeeded without SSH.

## Phase 5 - Remove SSH Artifacts and Complete Documentation Handoff

### Tasks

- [ ] Delete obsolete SSH code, remote-path environment keys, proxy sync
  scripts, Caddy SSH registration code, `install_ssh_public_key.sh`, and their
  now-obsolete tests only after Phase 4 passes.
- [ ] Update `env.deploy.example` and `env.deploy.secrets.example` with only
  the new Portainer configuration. Explain that `PORTAINER_ACCESS_TOKEN` is
  mandatory for automation, whereas the Portainer-owned GHCR pull credential
  is configured in the UI and is not copied into local deploy secrets.
- [ ] Update `README.md`, `docs/deploy/UBUNTU_SERVER.md`,
  `docs/deploy/STAGING.md`, `docs/deploy/HOOKS.md`,
  `docs/deploy/SHARED_CADDY_ROUTING.md`, and `docs/deploy/ENV_SCHEMA.md` so
  they describe one Portainer-only workflow. Each changed major document starts
  with its operating principles and links to the recovery runbook instead of
  duplicating it.
- [ ] Add a protected GitHub Environment Portainer-release job after the image
  build. It materializes `RUNTIME_ENV_DOTENV` and `RUNTIME_SECRETS_DOTENV` only
  under `$RUNNER_TEMP` with mode `600`, passes their paths to the Portainer-only
  deploy command, uses a cleanup trap, and never enables shell tracing. Keep
  build-push credentials separate from the Portainer release token.
- [ ] Run the deployment readiness and rollout-adoption checks, scan executable
  deployment code for SSH remnants, and archive this plan only after the full
  migration is accepted.

### Acceptance Criteria

- [ ] No executable deployment path, configuration example, or active
  deployment documentation describes SSH as a normal dependency.
- [ ] Historical changelog/archive references remain intact; they are not
  treated as active instructions.
- [ ] The break-glass runbook is visible, current, and clearly outside the
  routine release workflow.

### Verification

- [ ] `rg -n -i '\\bssh\\b|\\brsync\\b|UBUNTU_SSH|UBUNTU_REMOTE_DIR|STAGING_REMOTE_DIR|UBUNTU_SYNC_SECRETS' scripts docker docs README.md env.deploy.example`
- [ ] `source .venv/bin/activate && python scripts/deploy/validate_env.py`
- [ ] `source .venv/bin/activate && python scripts/deploy/ubuntu_deploy.py --help`
- [ ] Inspect the workflow diff to confirm runtime secret values are referenced
  only through the `secrets` context/environment and are never echoed, passed as
  CLI literals, written into the workspace, or uploaded as artifacts.
- [ ] `source .venv/bin/activate && python scripts/run_tests.py --priority-tests='["tests/pytests/test_ubuntu_deploy.py","tests/pytests/test_env_schema.py"]'`

### Exit Criteria

- [ ] The repository has one tested Portainer-only Ubuntu deployment story and
  a separate recovery story.

## Risks and Mitigations

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Portainer is down or its token expires | High | Fail preflight without touching production; use a documented local-console recovery path and rotate/test a replacement token. |
| Existing host bind mounts lose configuration or data | High | Replace config mounts with explicit stack variables and persistence mounts with named volumes; validate on a candidate before cutover. |
| Caddy migration briefly cuts off Portainer HTTPS | High | Use a maintenance window, preserve volumes and the existing container name, record rollback image/config, and keep local-console recovery available. |
| Private GHCR image cannot pull | High | Create and preflight a dedicated Portainer registry with a read-only package token; include its registry ID in stack requests. |
| Mutable image tags make promotion/rollback ambiguous | Medium | Publish and deploy git-SHA tags or digests only. |
| API fields differ by installed Portainer version | Medium | Observe the deployed version/edition and validate exact request shapes against its OpenAPI spec before implementation. |
| Shared downstream Caddy routes depend on dynamic host-file edits | Medium | Migrate each approved route into the declarative platform Caddy configuration; do not retain dynamic SSH registration. |

## Validation Plan

- Baseline completed: `source .venv/bin/activate && python -m pytest tests/pytests/test_ubuntu_deploy.py tests/pytests/test_caddy_register.py tests/pytests/test_env_schema.py -v` — 87 passed.
- Focused during implementation: deployment/Portainer helper/env-schema tests, plus Caddy image/Compose contract tests.
- Live evidence: read-only preflight, candidate-stack deployment, staging promotion, authenticated/unauthenticated ingress checks, and planned reboot recovery.
- Full confidence gate: `source .venv/bin/activate && python scripts/run_tests.py --priority-tests='["tests/pytests/test_ubuntu_deploy.py","tests/pytests/test_env_schema.py"]'`.

## Sources

- [Portainer: Add a Docker stack](https://docs.portainer.io/sts/user/docker/stacks/add) — stack sources, stack environment variables, GitOps/webhooks, and image re-pull/force-redeploy behavior.
- [Portainer: Automatic stack updates](https://docs.portainer.io/faqs/troubleshooting/stacks-deployments-and-updates/how-do-automatic-updates-for-stacks-applications-work) — Docker Standalone update semantics.
- [Portainer: Docker Standalone environments](https://docs.portainer.io/admin/environments/add/docker) — supported environment connection methods and host prerequisites.
- [Portainer CE API documentation](https://api-docs.portainer.io/?edition=ce&version=2.39.0) — version-sensitive stack API verification.
- [GitHub Actions: Using secrets](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets?tool=cli) — environment-secret access and safe process handling.
- [GitHub Actions: Secrets reference](https://docs.github.com/en/actions/reference/security/secrets) — environment-secret precedence, size limits, and masking limitations.
- [Azure Arc server managed identity](https://learn.microsoft.com/en-us/azure/azure-arc/servers/managed-identity-authentication) — host identity and Azure Key Vault access boundary.
- [Azure Container Apps managed identities](https://learn.microsoft.com/en-us/azure/container-apps/managed-identity) — native managed identity for Azure-hosted containers.

## Open Questions

- What Portainer CE/BE version and endpoint ID are installed on the local-network
  Ubuntu host, and does its observed API support the desired stack update body?
- Is the current `central-proxy` the only shared Caddy owner, or do other
  projects depend on dynamically registered routes that must migrate into the
  declarative platform Caddy image first?
- Which values, if any, beyond the documented runtime examples must remain
  available to the Ubuntu application after host `.env` sourcing is removed?
- Is accepting runtime secret copies in the Portainer stack database appropriate
  for this deployment, or must Phase 1 select an external secret provider before
  the Portainer-only migration can proceed?
- If Azure Arc is selected, what broker design lets only the intended container
  use the Arc identity without mounting host challenge material, using host
  networking, or granting Docker-host administration capability?
- Does the existing Portainer access token have the minimum rights required for
  stack update, registry association, network inspection, and lifecycle actions;
  should a dedicated automation account/token replace it?
