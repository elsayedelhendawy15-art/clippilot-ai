# Cloudflare Worker

Deploy with `npm install -g wrangler`, `wrangler login`, then `wrangler deploy`.
Set `TELEMETRY_URL=https://YOUR-WORKER.workers.dev/event` in the Python `.env`.

This starter keeps the latest event in isolate memory only. Use Durable Objects or D1 for persistence, and add authentication/rate limits before public deployment.
