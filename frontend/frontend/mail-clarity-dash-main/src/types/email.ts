/**
 * Re-export of the portable email types that live with the extension
 * components (src/components/extension/types.ts), so the dashboard and the
 * copy-out-ready extension folder always share one shape.
 */
export type {
  Priority,
  Tone,
  ThreadMessage,
  Source,
  Email,
} from "../components/extension/types";
export { CRITIC_CONFIDENCE_THRESHOLD } from "../components/extension/types";
