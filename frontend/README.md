# Scholar frontend

React + Vite frontend for the faculty/student academic assistant. No student or course fixture data is included; screens display API-backed content, empty states, or service errors.

## Run locally

```bash
cd frontend
npm install
npm run dev
```

The Vite development server proxies documented API paths to `http://localhost:8000` by default. Override that target with `VITE_API_PROXY_TARGET` when the FastAPI backend uses another origin. For a deployed frontend, set `VITE_API_BASE_URL` to the backend origin at build time, or configure the hosting layer to proxy the API paths.

Bearer tokens remain in application memory only; refreshing the page signs the user out rather than persisting the token in browser storage. Recent questions and flashcard state are also transient and clear when their page unmounts or the user signs out.

The assistant endpoints (`POST /agent/chat` and `POST /agent/confirm`) are scaffolded and may return `503 AGENT_NOT_CONFIGURED`; the chat panel surfaces that response and does not invent a reply or mark a proposal as saved. Other unavailable endpoints similarly show a retryable error state.

## Verify

```bash
npm test
npm run build
```
