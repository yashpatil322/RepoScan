# RepoScan — Frontend

A React + Three.js frontend for the RepoScan RAG backend (Tree-sitter + ChromaDB + Gemini).
This is **frontend only** — it talks to your existing FastAPI backend over HTTP; nothing
here runs a server or touches your Python code.

## What's inside

- **Overview** — hero with a live "embedding space" visualization (the actual signature
  visual of this build — code chunks as points in vector space, exactly what the backend
  retrieves by cosine similarity), plus system stats and your most recently indexed repos.
- **Ingest** — submit a GitHub URL, watch it move through `queued → cloning → parsing →
  embedding → completed`, with history kept per-browser.
- **Ask** — chat-style Q&A against `/query` or `/query/stream`, with inline citation chips
  and a source panel showing file, line range, chunk type, and similarity score.
- **Search** — raw `/search` (no LLM) with language/chunk-type filters, plus a "find
  similar" action that calls `/search/similar/{chunk_id}`.
- **Repos** — grid of indexed repos, delete with confirmation, and a slide-over chunk
  browser (`/repos/{id}/chunks`) with pagination.

## Setup

```bash
npm install
cp .env.example .env
# edit .env if your backend isn't on http://localhost:8000
npm run dev
```

Then open the printed local URL. Make sure the FastAPI backend (`uvicorn api.main:app
--reload --port 8000`) is running — the nav bar's status dot polls `GET /health` every
20 seconds and turns red if the API is unreachable.

## Build

```bash
npm run build
npm run preview   # serve the production build locally
```

## Stack

React 18 · React Router · Framer Motion · @react-three/fiber (Three.js) · Tailwind CSS ·
axios · recharts is not required (stats use plain cards, not charts, by design — see
notes below).

## Design notes

- Dark, terminal-adjacent palette (`#0a0d14` base, `#7c6fff` violet accent for anything
  vector/embedding-related, amber for citations, green for "completed"/healthy states).
- Type: Space Grotesk for display, Inter for body copy, JetBrains Mono for anything that
  is data — file paths, line ranges, repo IDs, code.
- The embedding-field canvas is ambient by default and "pulses" a cluster of nodes when
  you submit a question from the homepage — a nod to what retrieval is actually doing,
  not a decorative particle effect.
- All animation respects `prefers-reduced-motion`.

## Extending

The entire backend contract lives in `src/lib/api.js` — one function per endpoint,
already matching the shapes in your API reference (including the SSE parser for
`/query/stream`). Add a new page by adding a route in `src/App.jsx` and a link in
`src/components/NavBar.jsx`.
