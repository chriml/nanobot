# Nanobot Admin UI

Astro-based local admin for nanobot instances.

Use it to:
- See all discovered bots from one dashboard
- Open a per-bot control page
- Create, start, stop, and restart bot containers
- Inspect per-bot token usage and logs

Run locally:

```bash
cd website
npm install
npm run dev
```

Build static assets for the Python runtime:

```bash
cd website
npm install
npm run build
```

The built files land in `website/dist` and are served by nanobot at `/admin`.
