# StockScope frontend

React 19 + TypeScript + Vite + Tailwind. Talks to the Django API at `VITE_API_BASE_URL` (default `http://localhost:8000/api`).

```powershell
npm install
npm run dev                              # http://localhost:5173
npm run build                            # tsc -b && vite build
npx tsc --noEmit -p tsconfig.app.json    # type-check; `-p .` checks nothing (root tsconfig has files: [])
```

`npm run lint` (oxlint) may be blocked locally by Windows Smart App Control.

Layout and conventions (api modules, hooks, permission routing, styling tokens): see the root [CLAUDE.md](../CLAUDE.md). Route → page → backend map: [Backend/docs/architecture.md](../Backend/docs/architecture.md).
