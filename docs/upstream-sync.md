# Upstream Sync Workflow

Keep `main` as close to `upstream/main` as possible.

Put local-only behavior in additive files instead of editing upstream-hot files:

- [`Dockerfile.local`](/Users/cm/Documents/workspace/nanobot/Dockerfile.local)
- [`docker-compose.local.yml`](/Users/cm/Documents/workspace/nanobot/docker-compose.local.yml)
- [`docker/searxng/settings.yml`](/Users/cm/Documents/workspace/nanobot/docker/searxng/settings.yml)
- [`presets/local-stack.json`](/Users/cm/Documents/workspace/nanobot/presets/local-stack.json)
- [`presets/openai-sdk.json`](/Users/cm/Documents/workspace/nanobot/presets/openai-sdk.json)
- [`presets/anthropic-sdk.json`](/Users/cm/Documents/workspace/nanobot/presets/anthropic-sdk.json)
- [`nanobot/agent/spawned.py`](/Users/cm/Documents/workspace/nanobot/nanobot/agent/spawned.py)
- [`nanobot/providers/factory.py`](/Users/cm/Documents/workspace/nanobot/nanobot/providers/factory.py)
- [`scripts/apply-preset.py`](/Users/cm/Documents/workspace/nanobot/scripts/apply-preset.py)

Use presets to stamp your local defaults back onto `~/.nanobot/config.json` after syncing upstream, instead of patching core config-loading behavior.

Example:

```bash
./scripts/apply-preset.py local-stack openai-sdk
```

That keeps the default local setup on the direct OpenAI or Anthropic SDK path rather than routing through a gateway provider.
Spawned runtime agents inherit the main provider config by default and only override provider/auth per agent when explicitly requested, while still running in the same process/container.
Auto-update is enabled by default for clean git checkouts and uses `ff_only` mode unless you override it.
The auto-update loop only works when nanobot is running from a clean git checkout of this repo.

Use the local Docker overlay like this:

```bash
docker compose -f docker-compose.yml -f docker-compose.local.yml up -d nanobot-gateway
docker compose -f docker-compose.yml -f docker-compose.local.yml run --rm nanobot-cli status
```

To refresh your custom branch after upstream moves:

```bash
./scripts/sync-local-branch.sh
```
