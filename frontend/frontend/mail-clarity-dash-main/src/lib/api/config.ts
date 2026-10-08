/** Backend base URL. Defaults to the local backend; override with VITE_BACKEND_URL for other envs. */
export const BACKEND_URL = import.meta.env.VITE_BACKEND_URL ?? "http://localhost:8000";

/** Where "Sign in with Google" starts; the backend runs the flow and sets the session cookie. */
export const SIGN_IN_URL = `${BACKEND_URL}/auth/google/start`;
