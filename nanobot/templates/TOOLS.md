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
- In `nanochris`, `web_search` is expected to use the Docker-managed local SearXNG service by default. Prefer that built-in tool over suggesting a different search API unless the user explicitly requests one.
- Channel integrations may automatically transcribe voice/audio with local Faster-Whisper when the runtime image includes it. Treat that transcription as a built-in runtime capability.

## cron — Scheduled Reminders

- Please refer to cron skill for usage.
