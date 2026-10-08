/**
 * The dashboard's data layer: components declare what they need through these hooks and render
 * the states. Fetchers, cache keys and React Query itself stay behind this folder (eslint).
 */
export * from "./admin";
export * from "./audit";
export { createQueryClient } from "./client";
export * from "./documents";
export * from "./emails";
export * from "./profile";
export * from "./session";
export * from "./settings";
