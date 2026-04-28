# frontend

Next.js + TypeScript + Tailwind dashboard for AImail. Shows incoming threads, generated draft replies, and lets the user approve, edit, or reject them. Talks to the backend over REST only — no direct DB or Claude access.

## Run locally

_Not built yet._ Placeholder steps:

```bash
cd frontend
npm install            # TODO
npm run dev            # TODO — http://localhost:3000
```

## Key dependencies

- Next.js (App Router)
- React 18+
- TypeScript
- Tailwind CSS
- A REST client (fetch / TanStack Query — TBD)

## Env vars

Defined in `.env.local.example` (TODO). Expected keys:

- `NEXT_PUBLIC_BACKEND_URL`
- `NEXTAUTH_SECRET` (if auth is added)

## Folder structure

```
frontend/
├── app/                 # Next.js App Router routes
├── components/          # shared React components
├── lib/                 # API client, hooks, utils
├── styles/              # Tailwind config + globals
├── types/               # shared TS types (mirror backend contracts)
├── public/
├── package.json
└── tsconfig.json
```
