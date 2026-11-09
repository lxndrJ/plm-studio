<script lang="ts">
  import { goto } from "$app/navigation";
  import { api } from "$lib/api/client";
  import { auth } from "$lib/auth";

  let email = "";
  let password = "";
  let error = "";
  let busy = false;

  async function submit(): Promise<void> {
    error = "";
    busy = true;
    try {
      const t = await api.login(email, password);
      auth.set({ token: t.access_token, email: t.email, role: t.role });
      goto("/");
    } catch (e: any) {
      error = e?.message ?? "Login fehlgeschlagen";
    } finally {
      busy = false;
    }
  }
</script>

<div class="login-wrap">
  <div class="card login-card">
    <div class="logo-big"><span class="logo-mark">P</span> PLM Studio</div>
    <div class="tag">In-house PLM mit KI-Agenten — Phase 1 live.</div>
    <form on:submit|preventDefault={submit}>
      <label for="email">E-Mail</label>
      <input id="email" class="input" type="email" bind:value={email} required autocomplete="username" />
      <label for="pw">Passwort</label>
      <input id="pw" class="input" type="password" bind:value={password} required autocomplete="current-password" />
      {#if error}<div class="error" style="margin-top: 12px">{error}</div>{/if}
      <button class="btn btn-primary" style="width: 100%; margin-top: 18px" disabled={busy} type="submit">
        {busy ? "…" : "Anmelden"}
      </button>
    </form>
  </div>
</div>
