<script lang="ts">
  import { onMount } from "svelte";
  import { page } from "$app/stores";
  import { goto } from "$app/navigation";
  import { api, type Eco, type Ecr } from "$lib/api/client";
  import Badge from "$lib/components/Badge.svelte";
  import TransitionBar from "$lib/components/TransitionBar.svelte";

  const nr = $page.params.nr ?? "";
  const isEcr = nr.startsWith("ECR-");

  let ecr: Ecr | null = null;
  let eco: Eco | null = null;
  let error = "";
  let notice = "";
  let ecoReason = "";
  let affPart = "";
  let affRev = "";
  let affReason = "";

  const ecrTransitions: Record<string, { to: string; label: string }[]> = {
    open: [{ to: "in_review", label: "→ In Prüfung" }],
    in_review: [{ to: "approved", label: "→ Genehmigen" }, { to: "rejected", label: "→ Ablehnen" }],
    approved: [],
    rejected: [],
  };
  const ecoTransitions: Record<string, { to: string; label: string }[]> = {
    draft: [{ to: "approved", label: "→ Genehmigen" }],
    approved: [{ to: "executed", label: "→ Ausgeführt" }],
    executed: [],
  };

  async function load(): Promise<void> {
    error = "";
    try {
      if (isEcr) ecr = await api.getEcr(nr);
      else eco = await api.getEco(nr);
    } catch (e: any) {
      error = e?.message ?? "Nicht gefunden";
    }
  }

  async function tEcr(to: string, reason: string): Promise<void> {
    try {
      await api.transitionEcr(nr, to, reason || "UI-Transition");
      notice = `ECR → ${to}`;
      await load();
    } catch (e: any) {
      error = e?.message;
    }
  }

  async function tEco(to: string, reason: string): Promise<void> {
    try {
      await api.transitionEco(nr, to, reason || "UI-Transition");
      notice = `ECO → ${to}`;
      await load();
    } catch (e: any) {
      error = e?.message;
    }
  }

  async function makeEco(): Promise<void> {
    try {
      const e = await api.createEco(nr, ecoReason || undefined);
      notice = `${e.number} angelegt.`;
      goto(`/changes/${e.number}`);
    } catch (e: any) {
      error = e?.message;
    }
  }

  async function addAff(): Promise<void> {
    try {
      await api.addAffected(nr, affPart.trim(), affRev || undefined, affReason || undefined);
      affPart = "";
      affRev = "";
      affReason = "";
      notice = "Betroffene Revision hinzugefügt.";
      await load();
    } catch (e: any) {
      error = e?.message;
    }
  }

  async function removeAff(revisionId: string): Promise<void> {
    try {
      await api.removeAffected(nr, revisionId);
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

{#if isEcr && ecr}
  <div class="page-head">
    <div>
      <h1 class="mono">{ecr.number}</h1>
      <div class="tag">{ecr.description} · {fmt(ecr.created_at)}</div>
    </div>
    <div class="row">
      <Badge status={ecr.status} />
      <TransitionBar options={ecrTransitions[ecr.status] ?? []} onTransition={tEcr} />
    </div>
  </div>

  <div class="card">
    <div class="section-title">
      <h3>ECOs zu diesem ECR</h3>
      <div class="row">
        {#if ecr.status === "approved"}
          <input class="input input-sm" style="width: 200px" placeholder="Grund" bind:value={ecoReason} />
          <button class="btn btn-primary btn-sm" on:click={makeEco}>+ ECO anlegen</button>
        {:else}
          <span class="muted small">ECO erst nach Genehmigung des ECR möglich.</span>
        {/if}
      </div>
    </div>
    {#if !ecr.ecos || ecr.ecos.length === 0}<div class="empty">Noch keine ECOs.</div>{/if}
    <div class="table-wrap">
      <table class="table">
        <thead><tr><th>Nummer</th><th>Status</th><th>Erstellt</th></tr></thead>
        <tbody>
          {#each ecr.ecos ?? [] as e}
            <tr class="clickable" on:click={() => goto(`/changes/${e.number}`)}>
              <td class="mono pill-link">{e.number}</td>
              <td><Badge status={e.status} /></td>
              <td class="muted small">{fmt(e.created_at)}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  </div>
{:else if !isEcr && eco}
  <div class="page-head">
    <div>
      <h1 class="mono">{eco.number}</h1>
      <div class="tag">ECR: <a href={`/changes/${eco.ecr_number}`} class="mono pill-link">{eco.ecr_number}</a> · {fmt(eco.created_at)}</div>
    </div>
    <div class="row">
      <Badge status={eco.status} />
      <TransitionBar options={ecoTransitions[eco.status] ?? []} onTransition={tEco} />
    </div>
  </div>

  <div class="card">
    <div class="section-title">
      <h3>Betroffene Revisionen</h3>
      {#if eco.status === "draft"}
        <div class="row">
          <input class="input input-sm" style="width: 150px" placeholder="Sachnummer" bind:value={affPart} />
          <input class="input input-sm" style="width: 80px" placeholder="Rev" bind:value={affRev} />
          <input class="input input-sm" style="width: 140px" placeholder="Grund" bind:value={affReason} />
          <button class="btn btn-primary btn-sm" disabled={!affPart} on:click={addAff}>+ Hinzufügen</button>
        </div>
      {/if}
    </div>
    {#if !eco.affected || eco.affected.length === 0}<div class="empty">Keine betroffenen Revisionen.</div>{/if}
    <div class="table-wrap">
      <table class="table">
        <thead><tr><th>Artikel</th><th>Rev</th><th>Status</th><th></th></tr></thead>
        <tbody>
          {#each eco.affected ?? [] as a}
            <tr>
              <td class="mono pill-link">{a.part_number}</td>
              <td class="mono">{a.revision}</td>
              <td><Badge status={a.status} /></td>
              <td>
                {#if eco.status === "draft"}
                  <button class="btn btn-danger btn-sm" on:click={() => removeAff(a.revision_id)}>Entfernen</button>
                {/if}
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  </div>
{:else if !error}
  <div class="empty">Lade …</div>
{/if}
