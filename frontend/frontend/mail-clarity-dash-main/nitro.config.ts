// Vercel rewrites /api/* to the backend at its edge, so the browser talks to one site and the
// SameSite=Strict session cookies stay first-party (specs/features/free-hosting.md).
const backendOrigin = process.env.AIMAIL_BACKEND_ORIGIN?.replace(/\/+$/, "");

if (process.env.VERCEL && !backendOrigin) {
  throw new Error("Set AIMAIL_BACKEND_ORIGIN to the backend's https origin (e.g. the Render URL).");
}

export default {
  routeRules: {
    "/**": {
      headers: {
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "X-Content-Type-Options": "nosniff",
        "Content-Security-Policy":
          "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https: blob:; font-src 'self' data:; connect-src 'self' http://localhost:* https://*.onrender.com https://*.supabase.co;",
      },
    },
    ...(backendOrigin ? { "/api/**": { proxy: `${backendOrigin}/**` } } : {}),
  },
};
