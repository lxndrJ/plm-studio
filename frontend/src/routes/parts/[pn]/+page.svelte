<script lang="ts">
  import { onMount } from "svelte";
  import { page } from "$app/stores";
  import { goto } from "$app/navigation";
  import { api, type BomItem, type Part, type WhereUsed } from "$lib/api/client";
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
    } catch (e: any) {
      error = e?.message ?? "Fehler beim Laden";
    }
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
{:else if !error}
  <div class="empty">Lade …</div>
{/if}
