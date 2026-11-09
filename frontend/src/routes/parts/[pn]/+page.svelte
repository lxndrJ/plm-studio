<script lang="ts">
  import { onMount } from "svelte";
  import { page } from "$app/stores";
  import { goto } from "$app/navigation";
  import { api, type BomItem, type ClassAttribute, type Part, type PartClass, type WhereUsed } from "$lib/api/client";
  import Badge from "$lib/components/Badge.svelte";
  import TransitionBar from "$lib/components/TransitionBar.svelte";

  const pn = $page.params.pn ?? "";

  let part: Part | null = null;
  let bom: BomItem[] = [];
  let whereUsed: WhereUsed[] = [];
  let error = "";
  let notice = "";
  let newRevReason = "";
  let bomRev = "";
  let classes: PartClass[] = [];
  let attrForm: Record<string, any> = {};
  let attrReason = "";

  $: attrClass = part ? classes.find((c) => c.id === part!.class_id) : undefined;
  $: attrDefs = (attrClass?.attributes ?? []) as ClassAttribute[];
  $: draftRev = part ? [...part.revisions].reverse().find((r) => r.status === "draft") : undefined;

  const revTransitions: Record<string, { to: string; label: string }[]> = {
    draft: [{ to: "review", label: "→ Review" }, { to: "obsolete", label: "→ Obsolete" }],
    review: [{ to: "draft", label: "→ Zurück zu Draft" }, { to: "released", label: "→ Freigeben" }],
    released: [{ to: "obsolete", label: "→ Obsolete" }],
    obsolete: [],
  };

  async function load(): Promise<void> {
    error = "";
    try {
      part = await api.getPart(pn);
      if (!bomRev && part.revisions.length > 0) bomRev = part.revisions[part.revisions.length - 1].revision;
      await loadBom();
      whereUsed = await api.whereUsed(pn);
      if (classes.length === 0) classes = await api.partClasses();
      const draft = [...part.revisions].reverse().find((r) => r.status === "draft");
      attrForm = draft ? { ...(draft.attributes ?? {}) } : {};
    } catch (e: any) {
      error = e?.message ?? "Fehler beim Laden";
    }
  }

  async function saveAttributes(): Promise<void> {
    if (!draftRev) return;
    error = "";
    notice = "";
    try {
      await api.updateAttributes(pn, draftRev.id, attrForm, attrReason || undefined);
      notice = `Attribute von Rev ${draftRev.revision} gespeichert.`;
      attrReason = "";
      await load();
    } catch (e: any) {
      error = e?.message;
    }
  }

  function setAttr(key: string, value: any): void {
    attrForm = { ...attrForm, [key]: value };
  }

  async function loadBom(): Promise<void> {
    try {
      bom = await api.getBom(pn, bomRev || undefined);
    } catch (e: any) {
      bom = [];
    }
  }

  async function transition(revId: string, to: string, reason: string): Promise<void> {
    error = "";
    notice = "";
    try {
      await api.transitionRevision(revId, to, reason || "UI-Transition");
      notice = `Status auf '${to}' gesetzt.`;
      await load();
    } catch (e: any) {
      error = e?.message ?? "Transition fehlgeschlagen";
    }
  }

  async function addRevision(): Promise<void> {
    error = "";
    try {
      await api.createRevision(pn, newRevReason || "Neue Revision");
      newRevReason = "";
      notice = "Neue Revision angelegt.";
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

{#if error}<div class="error">{error}</div>{/if}
{#if notice}<div class="notice">{notice}</div>{/if}

{#if part}
  <div class="page-head">
    <div>
      <h1><span class="mono">{part.part_number}</span> — {part.name}</h1>
      <div class="tag">{part.description ?? "keine Beschreibung"} · angelegt {fmt(part.created_at)}</div>
    </div>
    <Badge status={part.part_type} />
  </div>

  <div class="grid2">
    <div class="card">
      <div class="section-title">
        <h3>Revisionen</h3>
        <div class="row">
          <input class="input input-sm" style="width: 200px" placeholder="Grund für neue Revision" bind:value={newRevReason} />
          <button class="btn btn-primary btn-sm" on:click={addRevision}>+ Neue Revision</button>
        </div>
      </div>
      <div class="table-wrap">
        <table class="table">
          <thead><tr><th>Rev</th><th>Status</th><th>Grund</th><th>Attribute</th><th>Transition</th></tr></thead>
          <tbody>
            {#each part.revisions as r}
              <tr>
                <td class="mono">{r.revision}</td>
                <td><Badge status={r.status} /></td>
                <td class="small">{r.change_reason}</td>
                <td class="mono small muted">{Object.keys(r.attributes ?? {}).length ? JSON.stringify(r.attributes) : "—"}</td>
                <td><TransitionBar options={revTransitions[r.status] ?? []} onTransition={(to, reason) => transition(r.id, to, reason)} /></td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    </div>

    <div class="card">
      <div class="section-title">
        <h3>Stückliste</h3>
        <select class="select" style="max-width: 120px" bind:value={bomRev} on:change={loadBom}>
          {#each part.revisions as r}<option value={r.revision}>Rev {r.revision}</option>{/each}
        </select>
      </div>
      {#if bom.length === 0}
        <div class="empty">Keine Stücklistenpositionen in Rev {bomRev}.</div>
      {:else}
        <div class="table-wrap">
          <table class="table">
            <thead><tr><th>Pos</th><th>Komponente</th><th>Rev</th><th>Menge</th><th>Status</th></tr></thead>
            <tbody>
              {#each bom as b}
                <tr class="clickable" on:click={() => goto(`/parts/${b.component_part_number}`)}>
                  <td>{b.position}</td>
                  <td class="mono pill-link">{b.component_part_number}</td>
                  <td class="mono">{b.component_revision}</td>
                  <td>{b.quantity} {b.unit}</td>
                  <td><Badge status={b.component_status} /></td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      {/if}

      <div class="section-title" style="margin-top: 18px">
        <h3>Where-Used</h3>
      </div>
      {#if whereUsed.length === 0}
        <div class="empty">Wird nirgends verbaut.</div>
      {:else}
        <div class="table-wrap">
          <table class="table">
            <thead><tr><th>Baugruppe</th><th>Rev</th><th>Status</th><th>Tiefe</th></tr></thead>
            <tbody>
              {#each whereUsed as w}
                <tr class="clickable" on:click={() => goto(`/parts/${w.parent_part_number}`)}>
                  <td class="mono pill-link">{w.parent_part_number}</td>
                  <td class="mono">{w.parent_revision}</td>
                  <td><Badge status={w.parent_status} /></td>
                  <td>{w.depth}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      {/if}
    </div>
  </div>
  {#if part && attrDefs.length > 0}
    <div class="card" style="margin-top: 14px">
      <div class="section-title">
        <h3>Attribute {#if attrClass}(Klasse {attrClass.code}){/if}</h3>
        {#if draftRev}<span class="muted small">bearbeitbar in Rev {draftRev.revision} (draft)</span>{:else}<span class="muted small">nur in draft-Revisionen bearbeitbar</span>{/if}
      </div>
      {#if draftRev}
        <div class="attr-grid">
          {#each attrDefs as a}
            <div class="attr-field">
              <label for="attr-{a.key}">{a.label} ({a.key}){a.required ? " *" : ""}{a.unit_code ? ` [${a.unit_code}]` : ""}</label>
              {#if a.attr_type === "enum"}
                <select id="attr-{a.key}" class="select" value={attrForm[a.key] ?? ""} on:change={(e) => setAttr(a.key, e.currentTarget.value || null)}>
                  <option value="">—</option>
                  {#each a.allowed_values ?? [] as v}<option value={v}>{v}</option>{/each}
                </select>
              {:else if a.attr_type === "boolean"}
                <input id="attr-{a.key}" type="checkbox" checked={attrForm[a.key] === true} on:change={(e) => setAttr(a.key, e.currentTarget.checked)} />
              {:else if a.attr_type === "number"}
                <input id="attr-{a.key}" class="input" type="number" step="any" value={attrForm[a.key] ?? ""} on:input={(e) => setAttr(a.key, e.currentTarget.value === "" ? null : Number(e.currentTarget.value))} />
              {:else}
                <input id="attr-{a.key}" class="input" value={attrForm[a.key] ?? ""} on:input={(e) => setAttr(a.key, e.currentTarget.value)} />
              {/if}
            </div>
          {/each}
        </div>
        <div class="row" style="margin-top: 12px">
          <input class="input input-sm" style="width: 220px" placeholder="Grund für Attribut-Änderung" bind:value={attrReason} />
          <button class="btn btn-primary btn-sm" on:click={saveAttributes}>Attribute speichern</button>
        </div>
      {:else}
        <div class="empty">Lege zuerst eine draft-Revision an, um Attribute zu bearbeiten.</div>
      {/if}
      {#if draftRev && Object.keys(draftRev.attributes ?? {}).length > 0}
        <div class="section-title" style="margin-top: 14px"><h3>Aktuelle Werte (Rev {draftRev.revision})</h3></div>
        <pre class="json">{JSON.stringify(draftRev.attributes, null, 2)}</pre>
      {/if}
    </div>
  {/if}
{:else if !error}
  <div class="empty">Lade …</div>
{/if}
