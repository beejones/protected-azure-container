# Deployment Customization Hooks

This repository allows downstream consumers (forks or layered repositories) to customize the deployment process without modifying the core `scripts/deploy/azure_deploy_container.py` script. This makes it easier to pull upstream updates while maintaining custom behavior.

## Overview

Hooks are Python callback methods that run at specific points in the deployment lifecycle. You can implement these hooks to:

- Override default configuration (e.g., container images, resources).
- Enforce custom validation rules.
- Modify the generated Azure Container Instances (ACI) YAML.
- Run pre-flight or post-deploy tasks.

## Configuration

To enable hooks, set the `DEPLOY_HOOKS_MODULE` environment variable (or use the CLI argument) to point to your Python module:

**Environment Variable:**
```bash
export DEPLOY_HOOKS_MODULE=scripts.deploy.deploy_customizations
```

**CLI Argument:**
```bash
./scripts/deploy/azure_deploy_container.py --hooks-module scripts.deploy.deploy_customizations
```

**Default:**
If `scripts/deploy/deploy_customizations.py` exists, it will be loaded automatically.

## Implementing Hooks

Create a Python module that exports a `get_hooks()` function returning an object (class instance or simple object) that implements any of the methods defined in the protocol. You only need to implement the hooks you care about.

### Example `deploy_customizations.py`

```python
import sys
from scripts.deploy.deploy_hooks import DeployContext, DeployPlan

class MyHooks:
    def pre_validate_env(self, ctx: DeployContext) -> None:
        """Called before .env files are validated. Good for injecting defaults."""
        if not ctx.env.get("MY_CUSTOM_VAR"):
             print("Injecting default for MY_CUSTOM_VAR")
             ctx.env["MY_CUSTOM_VAR"] = "default-value"

    def build_deploy_plan(self, ctx: DeployContext, plan: DeployPlan) -> None:
        """Called before YAML generation. Modify the plan here."""
        # Example: Enforce a specific image tag in production
        if ctx.env.get("ENVIRONMENT") == "production":
             plan.app_image = "my-prod-image:stable"
             
        # Example: Increase resources
        plan.app_memory = 4.0

    def post_render_yaml(self, ctx: DeployContext, plan: DeployPlan, yaml_text: str) -> str:
        """Called after YAML generation. Return modified YAML."""
        # Example: Add a custom environment variable to the YAML text
        return yaml_text.replace(
            "name: PUBLIC_DOMAIN", 
            "name: PUBLIC_DOMAIN\n        - name: EXTRA_VAR\n          value: 'foo'"
        )

def get_hooks():
    return MyHooks()
```

## Hook Reference

### `pre_validate_env(ctx)`
- **When**: Before strict schema validation of `.env` files.
- **Use for**: Injecting default environment variables, checking external prerequisites.

### `post_validate_env(ctx)`
- **When**: After environment variables are loaded and validated.
- **Use for**: Enforcing cross-field validation rules specific to your deployment.

### `build_deploy_plan(ctx, plan)`
- **When**: After parsing arguments and Docker Compose defaults, but before generating YAML.
- **Use for**: Overriding images, resources, ports, or networking settings. This is the **preferred** place for most customizations.

### `pre_render_yaml(ctx, plan)`
- **When**: Just before the YAML generation function is called.
- **Use for**: Last-minute plan adjustments.

### `post_render_yaml(ctx, plan, yaml_text) -> str`
- **When**: After YAML generation.
- **Use for**: String-based patching of result YAML if the `DeployPlan` doesn't expose a specific ACI feature you need.

### `pre_az_apply(ctx, plan, yaml_path)`
- **When**: Before `az container create` is executed.
- **Use for**: Logging, final confirmation, or side-effects (e.g. creating other resources).

### `post_deploy(ctx, plan, deploy_result)`
- **When**: After successful deployment.
- **Use for**: Post-deploy notifications, health checks.

### `on_error(ctx, exc)`
- **When**: If an exception occurs during deployment.
- **Use for**: Custom error reporting.

## Data Structures

### `DeployContext`
Read-only context containing:
- `repo_root`: Path to repository root.
- `env`: Dictionary of current environment variables.
- `args`: Parsed command-line arguments.

### `DeployPlan`
Mutable object representing the deployment configuration:
- `name`, `location`, `dns_label`
- `app_image`, `caddy_image`, `other_image`
- `app_cpu`, `app_memory`, etc.
- `extra_metadata`: A dictionary for custom data.

## Error Handling

By default, if a hook raises an exception, the deployment aborts.
To allow the deployment to continue despite hook failures (soft fail), set:

```bash
export DEPLOY_HOOKS_SOFT_FAIL=true
# or
./scripts/deploy/azure_deploy_container.py --hooks-soft-fail
```
