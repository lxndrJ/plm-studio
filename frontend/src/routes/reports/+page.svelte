<script lang="ts">
  import { onMount } from "svelte";
  import { api, download, type Report } from "$lib/api/client";

  let reports: Report[] = [];
  let pn = "";
  let ecrNr = "";
  let reason = "";
  let error = "";
  let notice = "";
  let openId: string | null = null;
  let openSnap: Record<string, any> | null = null;

  async function load(): Promise<void> {
    error = "";
    try {
      reports = await api.listReports();
    } catch (e: any) {
      error = e?.message ?? "Fehler";
    }
  }

  async function create(): Promise<void> {
    error = "";
    notice = "";
    try {
      const r = await api.createReport(pn.trim(), reason || undefined);
      notice = `${r.report_id} erstellt (PDF: ${r.pdf_available ? "ja" : "nein"}).`;
      pn = "";
      reason = "";
      await load();
    } catch (e: any) {
      error = e?.code === "no_released_revision" ? "Teil hat keine freigegebene (released) Revision — Reports enthalten nur released Content." : e?.message;
    }
  }

  async function createBom(): Promise<void> {
    error = "";
    notice = "";
    try {
      const r = await api.createBomReport(pn.trim(), reason || undefined);
      notice = `${r.report_id} (bom_explosion_v1) erstellt.`;
      await load();
    } catch (e: any) {
      error = e?.code === "no_released_revision" ? "Teil hat keine released Revision." : e?.message;
    }
  }

  async function createEcr(): Promise<void> {
    error = "";
    notice = "";
    try {
      const r = await api.createEcrReport(ecrNr.trim(), reason || undefined);
      notice = `${r.report_id} (ecr_v1) erstellt.`;
      await load();
    } catch (e: any) {
      error = e?.message;
    }
  }

  async function toggle(id: string): Promise<void> {
    if (openId === id) {
      openId = null;
      openSnap = null;
      return;
    }
    try {
      const r = await api.getReport(id);
      openId = id;
      openSnap = r.content_snapshot ?? null;
    } catch (e: any) {
      error = e?.message;
    }
  }

  async function dl(r: Report): Promise<void> {
    try {
      await download(`/reports/${r.report_id}/download`, `${r.report_id}.pdf`);
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
    <h1>Reports</h1>
    <div class="tag">Versionierte PDF-Reports (Typst) — nur freigegebene Inhalte, interne Daten (Preis/Lieferant) werden gefiltert</div>
  </div>
</div>

{#if error}<div class="error">{error}</div>{/if}
{#if notice}<div class="notice">{notice}</div>{/if}

<div class="card" style="margin-bottom: 14px">
  <h3>Report erstellen</h3>
  <div class="toolbar" style="margin-bottom: 8px">
    <input class="input" style="max-width: 240px" placeholder="Sachnummer mit released Revision" bind:value={pn} />
    <input class="input" style="max-width: 220px" placeholder="Grund (optional)" bind:value={reason} />
    <button class="btn btn-primary" disabled={!pn} on:click={create}>PDF-Teileblatt</button>
    <button class="btn btn-ghost" disabled={!pn} on:click={createBom}>Stückliste (mehrstufig)</button>
  </div>
  <div class="toolbar">
    <input class="input" style="max-width: 240px" placeholder="ECR-Nummer, z. B. ECR-00001" bind:value={ecrNr} />
    <button class="btn btn-ghost" disabled={!ecrNr} on:click={createEcr}>ECR/ECO-Bericht</button>
  </div>
</div>

<div class="card">
  {#if reports.length === 0}<div class="empty">Noch keine Reports.</div>{/if}
  <div class="table-wrap">
    <table class="table">
      <thead><tr><th>Report</th><th>Template</th><th>Erstellt</th><th>PDF</th><th></th></tr></thead>
      <tbody>
        {#each reports as r}
          <tr>
            <td class="mono pill-link">{r.report_id}</td>
            <td class="mono small">{r.template}</td>
            <td class="muted small">{fmt(r.created_at)}</td>
            <td>{r.pdf_available === false ? "—" : "✓"}</td>
            <td class="row">
              <button class="btn btn-ghost btn-sm" on:click={() => toggle(r.report_id)}>{openId === r.report_id ? "Snapshot zu" : "Snapshot"}</button>
              {#if r.pdf_available !== false}
                <button class="btn btn-primary btn-sm" on:click={() => dl(r)}>↓ PDF</button>
              {/if}
            </td>
          </tr>
          {#if openId === r.report_id && openSnap}
            <tr><td colspan="5"><pre class="json">{JSON.stringify(openSnap, null, 2)}</pre></td></tr>
          {/if}
        {/each}
      </tbody>
    </table>
  </div>
</div>
