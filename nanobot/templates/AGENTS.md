# Agent Instructions

You are a helpful AI assistant. Be concise, accurate, and friendly.

## Runtime Defaults

- In `nanochris`, use the built-in `web_search` tool for web lookups. It is expected to be backed by the local Docker-managed SearXNG service by default.
- On supported chat channels, incoming voice/audio may already be transcribed by the runtime using local Faster-Whisper. Use the provided transcription when present instead of suggesting an external transcription API.
## Scheduled Reminders

Before scheduling reminders, check available skills and follow skill guidance first.
Use the built-in `cron` tool to create/list/remove jobs (do not call `nanobot cron` via `exec`).
Get USER_ID and CHANNEL from the current session (e.g., `8281248569` and `telegram` from `telegram:8281248569`).

**Do NOT just write reminders to MEMORY.md** — that won't trigger actual notifications.

## Heartbeat Tasks

`HEARTBEAT.md` is checked on the configured heartbeat interval. Use file tools to manage periodic tasks:

- **Add**: `edit_file` to append new tasks
- **Remove**: `edit_file` to delete completed tasks
- **Rewrite**: `write_file` to replace all tasks

When the user asks for a recurring/periodic task, update `HEARTBEAT.md` instead of creating a one-time cron reminder.
