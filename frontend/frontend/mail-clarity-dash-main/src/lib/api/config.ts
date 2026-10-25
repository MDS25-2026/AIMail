/** Backend base URL. Defaults to the local backend; override with VITE_BACKEND_URL for other envs. */
export const BACKEND_URL = import.meta.env.VITE_BACKEND_URL ?? "http://localhost:8000";

/** False once the hosted backend is switched off (the FYP has ended); read per call so tests can stub it. */
export const isBackendLive = () => import.meta.env.VITE_BACKEND_OFFLINE !== "true";

/** Where "Sign in with Google" starts; the backend runs the flow and sets the session cookie. */
export const SIGN_IN_URL = `${BACKEND_URL}/auth/google/start`;

/** The public status page's data: no sign-in, no mailbox data, so even the demo asks the real backend. */
export const SERVICE_STATUS_PATH = "/service-status";
