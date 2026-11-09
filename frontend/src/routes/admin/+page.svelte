<script lang="ts">
  import { onMount } from "svelte";
  import { api, type AuditEntry, type PartClass, type User } from "$lib/api/client";
  import Badge from "$lib/components/Badge.svelte";

  let tab = "users";
  let users: User[] = [];
  let classes: PartClass[] = [];
  let audit: AuditEntry[] = [];
  let stats: { users: number; parts: number; open_confirmations: number } | null = null;
  let error = "";
  let notice = "";
  let resetPw: Record<string, string> = {};
  let newPwSelf = { old: "", neu: "" };

  const roles = ["viewer", "editor", "approver", "admin"];

  async function load(): Promise<void> {
    error = "";
    try {
      if (tab === "users") {
        [users, stats] = await Promise.all([api.listUsers(), api.stats()]);
      } else if (tab === "classes") {
        classes = await api.partClasses();
      } else if (tab === "audit") {
        audit = await api.auditLog(50);
      } else if (tab === "stats") {
        stats = await api.stats();
      }
    } catch (e: any) {
      error = e?.message ?? "Fehler";
    }
  }

  async function setTab(t: string): Promise<void> {
    tab = t;
    notice = "";
    await load();
  }

  async function changeRole(u: User, role: string): Promise<void> {
    error = "";
    try {
      await api.updateUser(u.id, { role });
      notice = `Rolle von ${u.email} → ${role}.`;
      await load();
    } catch (e: any) {
      error = e?.message;
      await load();
    }
  }

  async function toggleActive(u: User): Promise<void> {
    error = "";
    try {
      await api.updateUser(u.id, { is_active: !u.is_active });
      notice = `${u.email} ${u.is_active ? "deaktiviert" : "aktiviert"}.`;
      await load();
    } catch (e: any) {
      error = e?.message;
      await load();
    }
  }

  async function resetPassword(u: User): Promise<void> {
    const pw = resetPw[u.id]?.trim();
    if (!pw || pw.length < 8) {
      error = "Neues Passwort: mindestens 8 Zeichen.";
      return;
    }
    error = "";
    try {
      await api.resetUserPassword(u.id, pw);
      notice = `Passwort von ${u.email} zurückgesetzt (alte Sessions ungültig).`;
      resetPw = { ...resetPw, [u.id]: "" };
      await load();
    } catch (e: any) {
      error = e?.message;
    }
  }

  async function changeOwnPassword(): Promise<void> {
    error = "";
    try {
      await api.changePassword(newPwSelf.old, newPwSelf.neu);
      notice = "Eigenes Passwort geändert — bitte neu anmelden.";
      newPwSelf = { old: "", neu: "" };
      await api.logout().catch(() => {});
      location.href = "/";
    } catch (e: any) {
      error = e?.message;
    }
  }

  function fmt(ts: string | null): string {
    return ts ? new Date(ts).toLocaleString("de-DE", { dateStyle: "short", timeStyle: "short" }) : "—";
  }

  onMount(load);
</script>

<div class="page-head">
  <div>
    <h1>Admin</h1>
    <div class="tag">Benutzer, Klassen, Audit-Log, Statistiken</div>
  </div>
</div>

{#if error}<div class="error">{error}</div>{/if}
{#if notice}<div class="notice">{notice}</div>{/if}

<div class="tabs">
  {#each ["users", "classes", "audit", "stats"] as t}
    <button class:active={tab === t} on:click={() => setTab(t)}>{t === "users" ? "Benutzer" : t === "classes" ? "Klassen" : t === "audit" ? "Audit-Log" : "Statistik"}</button>
  {/each}
</div>

{#if tab === "users"}
  <div class="card">
    <div class="section-title"><h3>Benutzer</h3></div>
    <div class="table-wrap">
      <table class="table">
        <thead><tr><th>E-Mail</th><th>Rolle</th><th>Status</th><th>Passwort-Reset</th><th></th></tr></thead>
        <tbody>
          {#each users as u}
            <tr>
              <td class="mono">{u.email}</td>
              <td>
                <select class="select select-sm" value={u.role} on:change={(e) => changeRole(u, e.currentTarget.value)}>
                  {#each roles as r}<option value={r}>{r}</option>{/each}
                </select>
              </td>
              <td>{#if u.is_active}<Badge status="released" />{:else}<Badge status="obsolete" />{/if}</td>
              <td>
                <div class="toolbar">
                  <input class="input input-sm" style="width: 160px" type="password" placeholder="neues Passwort (min. 8)" bind:value={resetPw[u.id]} />
                  <button class="btn btn-ghost btn-sm" on:click={() => resetPassword(u)}>Setzen</button>
                </div>
              </td>
              <td><button class="btn btn-ghost btn-sm" on:click={() => toggleActive(u)}>{u.is_active ? "Deaktivieren" : "Aktivieren"}</button></td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
    <div class="section-title" style="margin-top: 18px"><h3>Eigenes Passwort</h3></div>
    <div class="toolbar">
      <input class="input input-sm" style="width: 180px" type="password" placeholder="altes Passwort" bind:value={newPwSelf.old} />
      <input class="input input-sm" style="width: 180px" type="password" placeholder="neues Passwort (min. 8)" bind:value={newPwSelf.neu} />
      <button class="btn btn-primary btn-sm" on:click={changeOwnPassword}>Ändern</button>
    </div>
  </div>
{:else if tab === "classes"}
  <div class="card">
    <div class="section-title"><h3>Artikelklassen &amp; typisierte Attribute</h3></div>
    <div class="table-wrap">
      <table class="table">
        <thead><tr><th>Code</th><th>Name</th><th>Attribute (key: typ, Einheit, Pflicht, Werte)</th></tr></thead>
        <tbody>
          {#each classes as c}
            <tr>
              <td class="mono">{c.code}</td>
              <td>{c.name}</td>
              <td class="small">
                {#each c.attributes ?? [] as a}
                  <div class="mono">{a.key}: {a.attr_type}{a.unit_code ? ` [${a.unit_code}]` : ""}{a.required ? " *" : ""}{a.allowed_values ? ` ∈ ${a.allowed_values.join("|")}` : ""}</div>
                {:else}<span class="muted">—</span>{/each}
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  </div>
{:else if tab === "audit"}
  <div class="card">
    <div class="section-title"><h3>Audit-Log (append-only, neueste zuerst)</h3></div>
    <div class="table-wrap">
      <table class="table">
        <thead><tr><th>Zeit</th><th>Typ</th><th>Aktion</th><th>Details</th><th>Grund</th></tr></thead>
        <tbody>
          {#each audit as a}
            <tr>
              <td class="small">{fmt(a.at)}</td>
              <td class="mono small">{a.entity_type}</td>
              <td class="small">{a.action}</td>
              <td class="mono small muted">{JSON.stringify(a.new_values ?? a.old_values ?? {})}</td>
              <td class="small muted">{a.reason ?? ""}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  </div>
{:else if tab === "stats" && stats}
  <div class="card">
    <div class="section-title"><h3>Statistik</h3></div>
    <dl class="kv">
      <dt>Benutzer</dt><dd>{stats.users}</dd>
      <dt>Artikel</dt><dd>{stats.parts}</dd>
      <dt>Offene Bestätigungen</dt><dd>{stats.open_confirmations}</dd>
    </dl>
  </div>
{/if}
