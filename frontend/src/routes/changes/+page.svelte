<script lang="ts">
  import { onMount } from "svelte";
  import { goto } from "$app/navigation";
  import { api, type Eco, type Ecr } from "$lib/api/client";
  import Badge from "$lib/components/Badge.svelte";

  let ecrs: Ecr[] = [];
  let ecos: Eco[] = [];
  let ecrStatus = "";
  let ecoStatus = "";
  let showNew = false;
  let fDesc = "";
  let fReason = "";
  let error = "";
  let notice = "";

  async function load(): Promise<void> {
    error = "";
    try {
      [ecrs, ecos] = await Promise.all([api.listEcrs(ecrStatus || undefined), api.listEcos(ecoStatus || undefined)]);
    } catch (e: any) {
      error = e?.message ?? "Fehler";
    }
  }

  onMount(load);

  async function create(): Promise<void> {
    error = "";
    notice = "";
    try {
      const e = await api.createEcr(fDesc, fReason || undefined);
      notice = `${e.number} angelegt.`;
      showNew = false;
      fDesc = "";
      fReason = "";
      await load();
      goto(`/changes/${e.number}`);
    } catch (e: any) {
      error = e?.message;
    }
  }

  function fmt(ts: string): string {
    return new Date(ts).toLocaleString("de-DE", { dateStyle: "short", timeStyle: "short" });
  }
</script>

<div class="page-head">
  <div>
    <h1>Änderungen</h1>
    <div class="tag">ECR (Antrag) → ECO (Umsetzung) mit Workflow-Matrix</div>
  </div>
  <button class="btn btn-primary" on:click={() => (showNew = !showNew)}>+ Neuer ECR</button>
</div>

{#if error}<div class="error">{error}</div>{/if}
{#if notice}<div class="notice">{notice}</div>{/if}

{#if showNew}
  <div class="card" style="margin-bottom: 14px">
    <h3>Neuer ECR</h3>
    <label for="fd">Beschreibung *</label>
    <textarea id="fd" class="input" rows="2" bind:value={fDesc} placeholder="Was soll geändert werden und warum?" />
    <label for="fr">Grund</label>
    <input id="fr" class="input" bind:value={fReason} />
    <div class="row" style="margin-top: 12px">
      <button class="btn btn-primary" disabled={!fDesc} on:click={create}>ECR anlegen</button>
      <button class="btn btn-ghost" on:click={() => (showNew = false)}>Abbrechen</button>
    </div>
  </div>
{/if}

<div class="grid2">
  <div class="card">
    <div class="section-title">
      <h3>ECRs</h3>
      <select class="select" style="max-width: 150px" bind:value={ecrStatus} on:change={load}>
        <option value="">Alle</option>
        <option value="open">open</option>
        <option value="in_review">in_review</option>
        <option value="approved">approved</option>
        <option value="rejected">rejected</option>
      </select>
    </div>
    {#if ecrs.length === 0}<div class="empty">Keine ECRs.</div>{/if}
    <div class="table-wrap">
      <table class="table">
        <thead><tr><th>Nummer</th><th>Beschreibung</th><th>Status</th><th>Erstellt</th></tr></thead>
        <tbody>
          {#each ecrs as e}
            <tr class="clickable" on:click={() => goto(`/changes/${e.number}`)}>
              <td class="mono pill-link">{e.number}</td>
              <td class="small">{e.description}</td>
              <td><Badge status={e.status} /></td>
              <td class="muted small">{fmt(e.created_at)}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  </div>

  <div class="card">
    <div class="section-title">
      <h3>ECOs</h3>
      <select class="select" style="max-width: 150px" bind:value={ecoStatus} on:change={load}>
        <option value="">Alle</option>
        <option value="draft">draft</option>
        <option value="approved">approved</option>
        <option value="executed">executed</option>
      </select>
    </div>
    {#if ecos.length === 0}<div class="empty">Keine ECOs.</div>{/if}
    <div class="table-wrap">
      <table class="table">
        <thead><tr><th>Nummer</th><th>ECR</th><th>Status</th><th>Erstellt</th></tr></thead>
        <tbody>
          {#each ecos as e}
            <tr class="clickable" on:click={() => goto(`/changes/${e.number}`)}>
              <td class="mono pill-link">{e.number}</td>
              <td class="mono pill-link">{e.ecr_number}</td>
              <td><Badge status={e.status} /></td>
              <td class="muted small">{fmt(e.created_at)}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  </div>
</div>
