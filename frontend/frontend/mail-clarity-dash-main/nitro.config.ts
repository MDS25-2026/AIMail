// Vercel rewrites /api/* to the backend at its edge, so the browser talks to one site and the
// SameSite=Strict session cookies stay first-party (specs/features/free-hosting.md).
const backendOrigin = process.env.AIMAIL_BACKEND_ORIGIN?.replace(/\/+$/, "");

if (process.env.VERCEL && !backendOrigin) {
  throw new Error("Set AIMAIL_BACKEND_ORIGIN to the backend's https origin (e.g. the Render URL).");
}

export default {
  routeRules: backendOrigin ? { "/api/**": { proxy: `${backendOrigin}/**` } } : {},
};
