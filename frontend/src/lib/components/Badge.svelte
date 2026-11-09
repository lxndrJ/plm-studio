<script lang="ts">
  export let status: string;
  const map: Record<string, string> = {
    draft: "b-draft",
    review: "b-review",
    in_review: "b-review",
    open: "b-open",
    proposed: "b-review",
    released: "b-released",
    approved: "b-released",
    obsolete: "b-obsolete",
    rejected: "b-rejected",
    executed: "b-executed",
    part: "b-part",
    assembly: "b-assembly",
    vector: "b-part",
    raster: "b-assembly",
    cad: "b-review",
    report: "b-executed",
    other: "b-draft",
  };
  $: cls = map[status] ?? "b-draft";
</script>

<span class="badge {cls}">{status}</span>
