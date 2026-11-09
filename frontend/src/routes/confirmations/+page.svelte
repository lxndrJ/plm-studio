<script lang="ts">
  import { onMount } from "svelte";
  import { api, type Confirmation } from "$lib/api/client";
  import Badge from "$lib/components/Badge.svelte";

  let items: Confirmation[] = [];
  let status = "proposed";
  let error = "";
  let notice = "";

  async function load(): Promise<void> {
    error = "";
    try {
      items = await api.listConfirmations(status || undefined);
    } catch (e: any) {
      error = e?.message ?? "Fehler";
    }
  }

  async function decide(c: Confirmation, approve: boolean): Promise<void> {
    error = "";
    notice = "";
    try {
      if (approve) await api.approve(c.id);
      else await api.reject(c.id);
      notice = `${c.action}: ${approve ? "genehmigt" : "abgelehnt"}.`;
      await load();
    } catch (e: any) {
      error = e?.message;
    }
  }

  function fmt(ts: string): string {
    return new Date(ts).toLocaleString("de-DE", { dateStyle: "short", timeStyle: "short" });
  }

  onMount(load);
</script>

<div class="page-head">
  <div>
    <h1>Bestätigungen</h1>
    <div class="tag">Vorgeschlagene Schreibzugriffe (z. B. vom KI-Agenten) — erst du genehmigst, dann wird ausgeführt</div>
  </div>
  <select class="select" style="max-width: 170px" bind:value={status} on:change={load}>
    <option value="proposed">Offen (proposed)</option>
    <option value="executed">Ausgeführt</option>
    <option value="rejected">Abgelehnt</option>
    <option value="">Alle</option>
  </select>
</div>

{#if error}<div class="error">{error}</div>{/if}
{#if notice}<div class="notice">{notice}</div>{/if}

{#if items.length === 0}
  <div class="card"><div class="empty">Keine Einträge.</div></div>
{:else}
  <div class="stack">
    {#each items as c}
      <div class="card">
        <div class="row" style="justify-content: space-between">
          <div>
            <strong>{c.summary}</strong>
            <div class="muted small mono">{c.action} · {fmt(c.created_at)} · läuft ab {fmt(c.expires_at)}</div>
          </div>
          <div class="row">
            <Badge status={c.status} />
            {#if c.status === "proposed"}
              <button class="btn btn-primary btn-sm" on:click={() => decide(c, true)}>Genehmigen</button>
              <button class="btn btn-danger btn-sm" on:click={() => decide(c, false)}>Ablehnen</button>
            {/if}
          </div>
        </div>
        <pre class="json" style="margin-top: 10px">{JSON.stringify(c.payload, null, 2)}</pre>
      </div>
    {/each}
  </div>
{/if}
