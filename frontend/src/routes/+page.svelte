<script lang="ts">
  import { onMount } from "svelte";
  import { goto } from "$app/navigation";
  import { api, type Confirmation, type PartSummary } from "$lib/api/client";
  import { auth } from "$lib/auth";
  import Badge from "$lib/components/Badge.svelte";

  let stats: { users: number; parts: number; open_confirmations: number } | null = null;
  let parts: PartSummary[] = [];
  let pending: Confirmation[] = [];
  let audit: any[] = [];
  let error = "";

  onMount(async () => {
    try {
      const [s, p, c] = await Promise.all([api.stats(), api.listParts(), api.listConfirmations("proposed")]);
      stats = s;
      parts = p.slice(0, 8);
      pending = c.slice(0, 5);
    } catch (e: any) {
      error = e?.message ?? "Fehler beim Laden";
    }
    if ($auth.role === "admin") {
      try {
        audit = await api.auditLog(12);
      } catch {
        audit = [];
      }
    }
  });

  function fmt(ts: string): string {
    return new Date(ts).toLocaleString("de-DE", { dateStyle: "short", timeStyle: "short" });
  }
</script>

<div class="page-head">
  <div>
    <h1>Dashboard</h1>
    <div class="tag">Übersicht über das PLM-System</div>
  </div>
  <button class="btn btn-primary" on:click={() => goto("/parts")}>Artikel öffnen →</button>
</div>

{#if error}<div class="error">{error}</div>{/if}

{#if stats}
  <div class="grid-stats">
    <div class="card stat"><div class="num">{stats.parts}</div><div class="lbl">Artikel</div></div>
    <div class="card stat"><div class="num">{stats.users}</div><div class="lbl">Benutzer</div></div>
    <div class="card stat"><div class="num">{stats.open_confirmations}</div><div class="lbl">Offene Bestätigungen</div></div>
    <div class="card stat"><div class="num" style="background: linear-gradient(135deg,#fff,#6ee7b7); -webkit-background-clip: text; background-clip: text;">live</div><div class="lbl">API-Status</div></div>
  </div>
{/if}

<div class="grid2">
  <div class="card">
    <div class="section-title">
      <h3>Letzte Artikel</h3>
      <a href="/parts" class="small">alle →</a>
    </div>
    {#if parts.length === 0}<div class="empty">Noch keine Artikel.</div>{/if}
    <div class="table-wrap">
      <table class="table">
        <tbody>
          {#each parts as p}
            <tr class="clickable" on:click={() => goto(`/parts/${p.part_number}`)}>
              <td class="mono pill-link">{p.part_number}</td>
              <td>{p.name}</td>
              <td><Badge status={p.part_type} /></td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  </div>

  <div class="card">
    <div class="section-title">
      <h3>Offene Bestätigungen</h3>
      <a href="/confirmations" class="small">alle →</a>
    </div>
    {#if pending.length === 0}<div class="empty">Keine offenen Vorschläge.</div>{/if}
    <div class="stack">
      {#each pending as c}
        <div style="border: 1px solid var(--border-soft); border-radius: 10px; padding: 10px 12px;">
          <div class="row" style="justify-content: space-between">
            <strong class="small">{c.summary}</strong>
            <Badge status={c.status} />
          </div>
          <div class="muted small mono">{c.action} · {fmt(c.created_at)}</div>
        </div>
      {/each}
    </div>
  </div>
</div>

{#if audit.length > 0}
  <div class="card" style="margin-top: 14px">
    <h3>Audit-Log (neueste)</h3>
    <div class="table-wrap">
      <table class="table">
        <thead><tr><th>Zeit</th><th>Entität</th><th>Aktion</th><th>Grund</th></tr></thead>
        <tbody>
          {#each audit as a}
            <tr>
              <td class="muted small">{fmt(a.at)}</td>
              <td class="mono small">{a.entity_type}</td>
              <td>{a.action}</td>
              <td class="muted small">{a.reason ?? ""}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  </div>
{/if}
