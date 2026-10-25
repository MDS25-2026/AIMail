/** A network call's pause, for answers made in the page: the server-rendered page hydrates first. */
export const NETWORK_PAUSE_MS = 150;

export const pause = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));
