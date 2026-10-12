# Free hosting for the final presentation: Vercel, Render and the laptop

- **Status:** in progress 2026-10-12
- **Issue:** #150; epic #138 line 92
- **Decision:** the owner chose option A on 2026-10-12: free tiers first, billing possibly later.

## Shape

```
browser ──► Vercel (dashboard, vercel.app)
              └─ /api/* rewritten at Vercel's edge ──► Render web service (free)
                                                        ├─ backend API  :$PORT
                                                        ├─ agent        127.0.0.1:8001
                                                        └─ worker       (drafting, retention, reconciler)
Render ──HTTPS + basic auth──► Cloudflare quick tunnel ──► laptop: Caddy ──► Presidio analyzer
laptop: listener (Pub/Sub pull) ──► Supabase ◄── Render
```

## Why each part is where it is

- **One origin for the browser.** The session cookies are `SameSite=Strict` and must stay so. The
  dashboard calls `/api/...` on its own vercel.app domain, and Vercel rewrites that to Render at the
  edge (Nitro's `routeRules` proxy, compiled to a Vercel rewrite). Cookies the backend sets through
  the rewrite belong to the vercel.app domain. The Google sign-in callback goes through it too:
  `BACKEND_PUBLIC_URL` is `https://<app>.vercel.app/api`.
- **One Render service for three processes.** Render's free tier allows web services only (no
  background workers, no private services), 512 MB, and 750 instance hours a month for the whole
  workspace: one always-on service. `backend/start-render.sh` runs the agent on loopback, the
  worker, and the API, and exits when any of them exits so Render restarts the lot. The agent stays
  on 127.0.0.1 and still requires `AGENT_TOKEN`, which a deployed environment must set anyway.
- **0.1 CPU, found on the first deploys (2026-10-12).** Render's health check timed out: the worker's
  category model (scikit-learn) loaded and ran on the event loop it shares with the API, so `/healthz`
  stalled, and both processes starting at once split the CPU. The model now loads and runs in a thread
  (`app/ml/categorise.py`), and `start-render.sh` starts the agent only once the API answers. Measured
  locally at `--cpus=0.1 --memory=512m` with 40 emails waiting: first healthy answer after about 48 s
  (98 s before), and no failed probe after it.
- **Settings are stripped of spaces and newlines** (`Settings._strip`): a leading space pasted into
  Render's `BACKEND_PUBLIC_URL` sent sign-in back to Supabase's default address.
- **Presidio on the laptop.** It needs about 2 GB. The backend refuses Refine, Search, Ask and
  uploads without it, and the agent's draft scan reports "scan unavailable". It is reached through
  a Cloudflare quick tunnel (no account; a new `trycloudflare.com` address each start) with Caddy in
  front checking basic auth, so the tunnel is not an open Presidio. The backend and the agent send
  `PRESIDIO_USER` and `PRESIDIO_PASSWORD` as basic auth; they are separate settings, never part of
  the URL, because httpx puts the URL in its error messages and those are logged.
- **The listener on the laptop.** It must stay up to pull new mail, which a free web service cannot
  (it sleeps after 15 minutes idle). It reaches Presidio on localhost as today.

## What the owner sets up (no code)

- **Vercel:** import the repo with root `frontend/frontend/mail-clarity-dash-main`; set
  `VITE_BACKEND_URL=/api` and `AIMAIL_BACKEND_ORIGIN=https://<service>.onrender.com`.
- **Render:** a Blueprint from `render.yaml`; fill each `sync: false` variable in the dashboard.
- **Supabase:** add `https://<app>.vercel.app/api/auth/callback` to the redirect URLs.
- **Laptop:** `make tunnel` starts Presidio, Caddy and the tunnel and prints the address to put in
  Render's `PRESIDIO_ANALYZER_URL`. The address changes on every start.
- **Keep-awake:** a free external pinger on `https://<service>.onrender.com/healthz` every 10 minutes,
  so the first click is not a one-minute cold start. One service always on fits the 750 hours.

## Limits, accepted for the demo

- The laptop must be on for masking and new mail. With it off, the dashboard still lists stored mail,
  and actions that need Presidio are refused with `masking_unavailable`.
- Typed text and documents travel from Render to the laptop over TLS (Cloudflare terminates and
  re-encrypts it). Email bodies do not: the listener masks them on the laptop before storage.
- Free Render has 0.1 CPU: drafting is slower than on a laptop.

## Not in this change

- The listener on a host, and a service account for Pub/Sub (needs paid always-on compute).
- Alerting.
