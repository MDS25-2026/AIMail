/** Who is signed in. needsReconnect: Google refused the stored token (7-day expiry or a revocation). */
export type SessionInfo = { email: string; hasMailbox: boolean; needsReconnect: boolean };
