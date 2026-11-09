<script lang="ts">
  import { onMount } from "svelte";
  import { api, download, type Document, type DocumentSummary } from "$lib/api/client";
  import Badge from "$lib/components/Badge.svelte";

  let docs: DocumentSummary[] = [];
  let query = "";
  let error = "";
  let notice = "";
  let showNew = false;
  let fTitle = "";
  let fType = "cad";
  let fReason = "";
  let openNr: string | null = null;
  let openDoc: Document | null = null;
  let fileInput: HTMLInputElement;

  async function load(): Promise<void> {
    error = "";
    try {
      docs = await api.listDocuments(query || undefined);
    } catch (e: any) {
      error = e?.message ?? "Fehler";
    }
  }

  async function create(): Promise<void> {
    try {
      const d = await api.createDocument(fTitle, fType, fReason || undefined);
      notice = `${d.doc_number} angelegt.`;
      showNew = false;
      fTitle = "";
      await load();
      await toggle(d.doc_number);
    } catch (e: any) {
      error = e?.message;
    }
  }

  async function toggle(nr: string): Promise<void> {
    if (openNr === nr) {
      openNr = null;
      openDoc = null;
      return;
    }
    try {
      openDoc = await api.getDocument(nr);
      openNr = nr;
    } catch (e: any) {
      error = e?.message;
    }
  }

  async function upload(): Promise<void> {
    const file = fileInput?.files?.[0];
    if (!file || !openDoc || openDoc.revisions.length === 0) return;
    try {
      await api.uploadFile(openDoc.doc_number, openDoc.revisions[openDoc.revisions.length - 1].revision, file);
      notice = `Datei '${file.name}' hochgeladen.`;
      await toggle(openDoc.doc_number);
    } catch (e: any) {
      error = e?.message;
    }
  }

  let debounce: ReturnType<typeof setTimeout>;
  function onSearch(): void {
    clearTimeout(debounce);
    debounce = setTimeout(load, 250);
  }

  onMount(load);
</script>

<div class="page-head">
  <div>
    <h1>Dokumente</h1>
    <div class="tag">CAD / Zeichnungen / Dateien mit Revisionen und Preview-Pipeline</div>
  </div>
  <button class="btn btn-primary" on:click={() => (showNew = !showNew)}>+ Neues Dokument</button>
</div>

{#if error}<div class="error">{error}</div>{/if}
{#if notice}<div class="notice">{notice}</div>{/if}

{#if showNew}
  <div class="card" style="margin-bottom: 14px">
    <h3>Neues Dokument</h3>
    <div class="form-grid">
      <div>
        <label for="ft">Titel *</label>
        <input id="ft" class="input" bind:value={fTitle} />
      </div>
      <div>
        <label for="fdt">Typ</label>
        <select id="fdt" class="select" bind:value={fType}>
          <option value="cad">CAD</option>
          <option value="vector">Vector</option>
          <option value="raster">Raster</option>
          <option value="report">Report</option>
          <option value="other">Other</option>
        </select>
      </div>
      <div class="full">
        <label for="fr">Grund</label>
        <input id="fr" class="input" bind:value={fReason} />
      </div>
    </div>
    <div class="row" style="margin-top: 12px">
      <button class="btn btn-primary" disabled={!fTitle} on:click={create}>Anlegen</button>
      <button class="btn btn-ghost" on:click={() => (showNew = false)}>Abbrechen</button>
    </div>
  </div>
{/if}

<div class="card">
  <div class="toolbar">
    <input class="input" style="max-width: 300px" placeholder="Suche …" bind:value={query} on:input={onSearch} />
  </div>
  {#if docs.length === 0}<div class="empty">Keine Dokumente.</div>{/if}
  <div class="table-wrap">
    <table class="table">
      <thead><tr><th>Nummer</th><th>Titel</th><th>Typ</th><th></th></tr></thead>
      <tbody>
        {#each docs as d}
          <tr class="clickable" on:click={() => toggle(d.doc_number)}>
            <td class="mono pill-link">{d.doc_number}</td>
            <td>{d.title}</td>
            <td><Badge status={d.doc_type} /></td>
            <td>{openNr === d.doc_number ? "▲" : "▼"}</td>
          </tr>
          {#if openNr === d.doc_number && openDoc}
            <tr>
              <td colspan="4">
                {#each openDoc.revisions as r}
                  <div class="row" style="margin: 6px 0">
                    <span class="mono">Rev {r.revision}</span>
                    <Badge status={r.status} />
                    <span class="muted small">{r.change_reason}</span>
                  </div>
                  {#each r.files as f}
                    <div class="row" style="margin: 4px 0 4px 16px">
                      <span class="small">{f.filename}</span>
                      <span class="muted small mono">{f.mime_type}</span>
                      <button class="btn btn-ghost btn-sm" on:click={() => download(`/doc-files/${f.id}/download`, f.filename)}>↓</button>
                    </div>
                  {/each}
                {/each}
                <div class="row" style="margin-top: 10px">
                  <input type="file" bind:this={fileInput} class="small" />
                  <button class="btn btn-primary btn-sm" on:click={upload}>Hochladen</button>
                </div>
              </td>
            </tr>
          {/if}
        {/each}
      </tbody>
    </table>
  </div>
</div>
