# frontend/AGENTS.md

Instructions and conventions for the React 18 + Vite 5 frontend.

## Key Rules

1. **Vite Base Path is strictly `'./'`.**
   - File: `frontend/vite.config.js`
   - Setting: `base: './'`
   - *Why*: FastAPI mounts the compiled single-page application at root or nested endpoints. An absolute base path `/` causes HTTP 404 on asset bundles, leading to a blank white screen with no obvious error (Incident Log 09).

2. **API Client Tunnel Bypass Header is Mandatory.**
   - File: `frontend/src/api/client.js`
   - Header: `bypass-tunnel-reminder: 'true'`
   - *Why*: Localtunnel and similar proxy tunnels serve anti-abuse warning interstitial HTML pages that intercept API requests and fail CORS preflight checks (Incident Logs 11 & 16).

3. **Build Artifacts & Testing.**
   - Always run `npm run build` in `frontend/` before verifying mounted production deployments.
   - Built assets reside in `frontend/dist/` and are mounted by FastAPI at `backend/main.py`.

## Component Responsibilities

- `PdfUploader.jsx`: Drag-and-drop file upload with format validation, error banners, and progress feedback.
- `RagChat.jsx`: Interactive chat interface with multi-turn history, formatted markdown rendering, and clickable source citation chips.
- `SummaryRoadmapView.jsx`: High-level synopsis, document identity cards, and structured action roadmap visualization.
