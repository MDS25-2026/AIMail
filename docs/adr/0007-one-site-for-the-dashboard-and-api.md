# ADR 0007 — The dashboard and the API are served from one site

- **Status:** Proposed
- **Date:** 2026-10-08
- **Deciders:** veyroxie (proposer); Lane D and infra owners to confirm
- **Extends:** [ADR 0005](0005-dashboard-google-sign-in.md) (the session lives in HttpOnly cookies)

## Context

The session and refresh cookies are `HttpOnly`, `Secure` outside dev and `SameSite=Strict`
(`backend/app/sign_in.py`). A browser sends a Strict cookie only on requests from the same *site*
(the same registrable domain). In dev every service is on `localhost`, one site, so sign-in works.
Deployed on two hosts' default domains, for example the dashboard on `*.vercel.app` and the API on
`*.onrender.com`, the two are different sites: the cookie is never sent and nobody stays signed in.
Nothing in the code is wrong; the deployment layout decides it, so it has to be decided before a host
is chosen.

## Decision

Serve the dashboard and the API under one registrable domain, as subdomains such as
`app.<domain>` and `api.<domain>`, keep the cookies host-only on the API with `SameSite=Strict`, and
list the dashboard's origin in `FRONTEND_ORIGINS` for CORS.

## Rationale

- Keeps the strongest cookie setting: Strict cookies are never sent from another site, which is most of
  the CSRF defence (the `X-AIMail-Client` header check is the rest).
- Needs no code change, only DNS and three settings (`FRONTEND_ORIGINS`, `BACKEND_PUBLIC_URL`, `DASHBOARD_URL`).
- Each service keeps its own host, so either can move or scale separately.

## Alternatives considered

| Alternative | Why rejected |
|-------------|--------------|
| Two hosts' default domains with `SameSite=None` | Sends the session on cross-site requests, so CSRF rests on one header check, and browsers that block third-party cookies drop it anyway. |
| One origin, with a reverse proxy sending `/api` to the backend | Also works, with no CORS at all; kept as the fallback if the chosen host cannot give both services one domain. It ties the two services to one proxy. |
| Bearer tokens in the browser instead of cookies | Puts the session where any injected script can read it; ADR 0005 chose cookies to avoid this. |

## Consequences

**Positive:** sign-in works the same deployed as in dev; the cookie settings stay as they are.

**Negative:** the project needs a domain it controls, not only the hosts' free subdomains.

## Open question

The Chrome side panel (ADR 0003) calls the API from a `chrome-extension://` page. Whether its requests
carry Strict cookies depends on Chrome's handling of extension requests with host permission; confirm
on the deployed domain before relying on it.

## Revisit conditions

- The chosen host cannot serve both services under one domain (take the reverse-proxy alternative).
- A second dashboard origin is added (for example a mobile shell) on another site.
