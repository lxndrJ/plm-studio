// The UI is a pure client-side SPA (JWT in localStorage, all data via /api).
// SSR is disabled: kit 2.70's internal runes code breaks production SSR with
// svelte 4, and there is nothing to render server-side here anyway.
export const ssr = false;
export const prerender = false;
