<script lang="ts">
  export let options: { to: string; label: string }[] = [];
  export let onTransition: (to: string, reason: string) => void;
  let pending: string | null = null;
  let reason = "";
  function start(to: string): void {
    pending = to;
    reason = "";
  }
  function submit(): void {
    if (pending) onTransition(pending, reason);
    pending = null;
  }
</script>

{#if options.length > 0}
  <div class="transbar">
    {#each options as o}
      {#if pending === o.to}
        <input class="input input-sm" style="width: 220px" placeholder="Begründung …" bind:value={reason} on:keydown={(e) => e.key === "Enter" && submit()} />
        <button class="btn btn-primary btn-sm" on:click={submit}>OK</button>
        <button class="btn btn-ghost btn-sm" on:click={() => (pending = null)}>✕</button>
      {:else}
        <button class="btn btn-ghost btn-sm" on:click={() => start(o.to)}>{o.label}</button>
      {/if}
    {/each}
  </div>
{/if}
