# Tool Usage Notes

Tool signatures are provided automatically via function calling.
This file documents non-obvious constraints and usage patterns.

## exec — Safety Limits

- Commands have a configurable timeout (default 60s)
- Dangerous commands are blocked (rm -rf, format, dd, shutdown, etc.)
- Output is truncated at 10,000 characters
- `restrictToWorkspace` config can limit file access to the workspace

## Native Runtime Tools

- `web_search` and `web_fetch` are built in. Use them directly instead of asking to install search tooling inside the agent session.
- If `tools.web.search.provider` is set to `searxng`, that backend is already behind `web_search`. In `nanochris`, it may already be running as a Docker-managed local service.
- Channel integrations may automatically transcribe voice/audio with local Whisper when the runtime image includes it.

## cron — Scheduled Reminders

- Please refer to cron skill for usage.
