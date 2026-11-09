<script lang="ts">
  import { goto } from "$app/navigation";
  import { api, type BomDiff, type BomItem, type Part, type WhereUsed } from "$lib/api/client";
  import Badge from "$lib/components/Badge.svelte";

  let pn = "";
  let part: Part | null = null;
  let bom: BomItem[] = [];
  let whereUsed: WhereUsed[] = [];
  let diff: BomDiff | null = null;
  let revA = "";
  let revB = "";
  let error = "";

  async function search(): Promise<void> {
    error = "";
    diff = null;
    try {
      part = await api.getPart(pn.trim());
      bom = await api.getBom(part.part_number);
      whereUsed = await api.whereUsed(part.part_number);
      if (part.revisions.length >= 2) {
        revA = part.revisions[0].revision;
        revB = part.revisions[part.revisions.length - 1].revision;
      } else if (part.revisions.length === 1) {
        revA = revB = part.revisions[0].revision;
      }
    } catch (e: any) {
      part = null;
      bom = [];
      whereUsed = [];
      error = e?.message ?? "Nicht gefunden";
    }
  }

  async function doDiff(): Promise<void> {
    error = "";
    try {
      diff = await api.bomDiff(pn.trim(), revA, revB);
    } catch (e: any) {
      error = e?.message;
    }
  }
</script>

<div class="page-head">
  <div>
    <h1>Stücklisten</h1>
    <div class="tag">BOM, Where-Used und Revisionsvergleich</div>
  </div>
</div>

{#if error}<div class="error">{error}</div>{/if}

<div class="card" style="margin-bottom: 14px">
  <div class="toolbar">
    <input class="input" style="max-width: 260px" placeholder="Sachnummer, z. B. ASM-000001" bind:value={pn} on:keydown={(e) => e.key === "Enter" && search()} />
    <button class="btn btn-primary" on:click={search}>Anzeigen</button>
  </div>
</div>

{#if part}
  <div class="grid2">
    <div class="card">
      <div class="section-title"><h3>Stückliste {part.part_number}</h3><Badge status={part.part_type} /></div>
      {#if bom.length === 0}<div class="empty">Leer.</div>{/if}
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
    </div>
    <div class="card">
      <div class="section-title"><h3>Where-Used</h3></div>
      {#if whereUsed.length === 0}<div class="empty">Wird nirgends verbaut.</div>{/if}
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
    </div>
  </div>

  <div class="card" style="margin-top: 14px">
    <div class="section-title"><h3>BOM-Vergleich</h3></div>
    <div class="toolbar">
      <select class="select" style="max-width: 110px" bind:value={revA}>
        {#each part.revisions as r}<option value={r.revision}>Rev {r.revision}</option>{/each}
      </select>
      <span class="muted">vs.</span>
      <select class="select" style="max-width: 110px" bind:value={revB}>
        {#each part.revisions as r}<option value={r.revision}>Rev {r.revision}</option>{/each}
      </select>
      <button class="btn btn-ghost btn-sm" on:click={doDiff}>Vergleichen</button>
    </div>
    {#if diff}
      <div class="grid2">
        <div>
          <h3 style="color: var(--green)">Hinzugefügt ({diff.added.length})</h3>
          {#each diff.added as a}<pre class="json">{JSON.stringify(a)}</pre>{/each}
        </div>
        <div>
          <h3 style="color: var(--red)">Entfernt ({diff.removed.length})</h3>
          {#each diff.removed as a}<pre class="json">{JSON.stringify(a)}</pre>{/each}
          <h3 style="color: var(--amber); margin-top: 10px">Geändert ({diff.changed.length})</h3>
          {#each diff.changed as a}<pre class="json">{JSON.stringify(a)}</pre>{/each}
        </div>
      </div>
    {/if}
  </div>
{/if}
