import { browser } from "$app/environment";
import { writable } from "svelte/store";

export interface AuthState {
  token: string | null;
  email: string | null;
  role: string | null;
}

const stored = browser ? localStorage.getItem("plm_auth") : null;

export const auth = writable<AuthState>(stored ? JSON.parse(stored) : { token: null, email: null, role: null });

auth.subscribe((v) => {
  if (!browser) return;
  if (v.token) localStorage.setItem("plm_auth", JSON.stringify(v));
  else localStorage.removeItem("plm_auth");
});

export function logout(): void {
  auth.set({ token: null, email: null, role: null });
}
