<script lang="ts">
  import { onMount } from "svelte";
  import { goto } from "$app/navigation";
  import { api, download, type PartClass, type PartSummary } from "$lib/api/client";
  import Badge from "$lib/components/Badge.svelte";

  let parts: PartSummary[] = [];
  let classes: PartClass[] = [];
  let query = "";
  let classCode = "";
  let partType = "";
  let status = "";
  let page = 1;
  const pageSize = 25;
  let total = 0;
  let showNew = false;
  let error = "";
  let notice = "";

  let fName = "";
  let fDesc = "";
  let fType = "part";
  let fClass = "";
  let fReason = "";
  let fAttrs = "";

  async function load(): Promise<void> {
    error = "";
    try {
      const r = await api.listPartsPage({
        query: query || undefined,
        classCode: classCode || undefined,
        partType: partType || undefined,
        status: status || undefined,
        page,
        pageSize,
      });
      parts = r.items;
      total = r.total;
      page = r.page;
    } catch (e: any) {
      error = e?.message ?? "Fehler beim Laden";
    }
  }

  async function exportFile(format: "csv" | "json"): Promise<void> {
    try {
      await download(`/export/parts?format=${format}`, `parts.${format}`);
    } catch (e: any) {
      error = e?.message;
    }
  }

  onMount(async () => {
    try {
      classes = await api.partClasses();
      fClass = classes[0]?.code ?? "";
    } catch {
      classes = [];
    }
    await load();
  });

  let debounce: ReturnType<typeof setTimeout>;
  function onSearch(): void {
    clearTimeout(debounce);
    debounce = setTimeout(() => {
      page = 1;
      load();
    }, 250);
  }

  function resetFilters(): void {
    query = "";
    classCode = "";
    partType = "";
    status = "";
    page = 1;
    load();
  }

  async function create(): Promise<void> {
    error = "";
    notice = "";
    try {
      let attributes: Record<string, unknown> | undefined;
      if (fAttrs.trim()) attributes = JSON.parse(fAttrs);
      const p = await api.createPart({ name: fName, description: fDesc || undefined, part_type: fType, class_code: fClass, attributes, reason: fReason || undefined });
      notice = `${p.part_number} angelegt.`;
      showNew = false;
      fName = "";
      fDesc = "";
      fReason = "";
      fAttrs = "";
      await load();
      goto(`/parts/${p.part_number}`);
    } catch (e: any) {
      error = e?.code === "duplicate_part" ? `Duplikat: ${JSON.stringify(e.details?.candidates)}` : e?.message;
    }
  }
</script>

<div class="page-head">
  <div>
    <h1>Artikel</h1>
    <div class="tag">Teile und Baugruppen — Nummern werden automatisch vergeben</div>
  </div>
  <div class="row">
    <button class="btn btn-ghost btn-sm" on:click={() => exportFile("csv")}>↓ CSV</button>
    <button class="btn btn-ghost btn-sm" on:click={() => exportFile("json")}>↓ JSON</button>
    <button class="btn btn-primary" on:click={() => (showNew = !showNew)}>+ Neuer Artikel</button>
  </div>
</div>

{#if error}<div class="error">{error}</div>{/if}
{#if notice}<div class="notice">{notice}</div>{/if}

{#if showNew}
  <div class="card" style="margin-bottom: 14px">
    <h3>Neuer Artikel</h3>
    <div class="form-grid">
      <div>
        <label for="fn">Bezeichnung *</label>
        <input id="fn" class="input" bind:value={fName} placeholder="z. B. Gehäuse" />
      </div>
      <div>
        <label for="ft">Typ</label>
        <select id="ft" class="select" bind:value={fType}>
          <option value="part">Teil</option>
          <option value="assembly">Baugruppe</option>
        </select>
      </div>
      <div>
        <label for="fc">Klasse *</label>
        <select id="fc" class="select" bind:value={fClass}>
          {#each classes as c}<option value={c.code}>{c.code} — {c.name}</option>{/each}
        </select>
      </div>
      <div>
        <label for="fr">Grund</label>
        <input id="fr" class="input" bind:value={fReason} placeholder="optional" />
      </div>
      <div class="full">
        <label for="fd">Beschreibung</label>
        <input id="fd" class="input" bind:value={fDesc} />
      </div>
      <div class="full">
        <label for="fa">Attribute (JSON, optional)</label>
        <input id="fa" class="input mono" bind:value={fAttrs} placeholder="JSON, z. B. material=Alu" />
      </div>
    </div>
    <div class="row" style="margin-top: 14px">
      <button class="btn btn-primary" disabled={!fName || !fClass} on:click={create}>Anlegen</button>
      <button class="btn btn-ghost" on:click={() => (showNew = false)}>Abbrechen</button>
    </div>
  </div>
{/if}

<div class="card">
  <div class="toolbar">
    <input class="input" style="max-width: 280px" placeholder="Suche (Nummer, Name) …" bind:value={query} on:input={onSearch} />
    <select class="select" style="max-width: 200px" bind:value={classCode} on:change={() => { page = 1; load(); }}>
      <option value="">Alle Klassen</option>
      {#each classes as c}<option value={c.code}>{c.code} — {c.name}</option>{/each}
    </select>
    <select class="select" style="max-width: 130px" bind:value={partType} on:change={() => { page = 1; load(); }}>
      <option value="">Alle Typen</option>
      <option value="part">Teil</option>
      <option value="assembly">Baugruppe</option>
    </select>
    <select class="select" style="max-width: 130px" bind:value={status} on:change={() => { page = 1; load(); }}>
      <option value="">Jeder Status</option>
      <option value="draft">draft</option>
      <option value="review">review</option>
      <option value="released">released</option>
      <option value="obsolete">obsolete</option>
    </select>
    <span class="muted small">{total} Treffer</span>
  </div>
  {#if parts.length === 0}
    <div class="empty">Keine Artikel gefunden. {#if query || classCode || partType || status}<a href="/parts" on:click|preventDefault={resetFilters}>Filter zurücksetzen</a>{/if}</div>
  {:else}
    <div class="table-wrap">
      <table class="table">
        <thead><tr><th>Nummer</th><th>Bezeichnung</th><th>Typ</th></tr></thead>
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
    <div class="pager">
      <button class="btn btn-ghost btn-sm" disabled={page <= 1} on:click={() => { page -= 1; load(); }}>← Zurück</button>
      <span>Seite {page} · {total} gesamt</span>
      <button class="btn btn-ghost btn-sm" disabled={page * pageSize >= total} on:click={() => { page += 1; load(); }}>Weiter →</button>
    </div>
  {/if}
</div>
