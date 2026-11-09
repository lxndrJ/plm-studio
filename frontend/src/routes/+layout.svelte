<script lang="ts">
  import "../app.css";
  import { page } from "$app/stores";
  import { auth, logout } from "$lib/auth";
  import { goto } from "$app/navigation";
  import Login from "$lib/components/Login.svelte";

  const nav = [
    { href: "/", label: "Dashboard", icon: "▦" },
    { href: "/parts", label: "Artikel", icon: "◈" },
    { href: "/bom", label: "Stücklisten", icon: "≣" },
    { href: "/changes", label: "Änderungen", icon: "⇄" },
    { href: "/confirmations", label: "Bestätigungen", icon: "✓" },
    { href: "/reports", label: "Reports", icon: "◫" },
    { href: "/documents", label: "Dokumente", icon: "🗎" },
  ];

  function isActive(href: string): boolean {
    const p = $page.url.pathname;
    if (href === "/") return p === "/";
    return p === href || p.startsWith(href + "/");
  }

  function doLogout(): void {
    logout();
    goto("/");
  }
</script>

{#if $auth.token}
  <div class="shell">
    <aside class="sidebar">
      <div class="logo"><span class="logo-mark">P</span> PLM&nbsp;Studio</div>
      <nav>
        {#each nav as n}
          <a href={n.href} class:active={isActive(n.href)}><span class="ico">{n.icon}</span>{n.label}</a>
        {/each}
      </nav>
      <div class="side-foot">
        <div class="user-chip">
          <div class="avatar">{($auth.email ?? "?").slice(0, 1).toUpperCase()}</div>
          <div>
            <div class="u-email">{$auth.email}</div>
            <div class="u-role">{$auth.role}</div>
          </div>
        </div>
        <button class="btn btn-ghost btn-sm" on:click={doLogout}>Abmelden</button>
      </div>
    </aside>
    <main class="main"><slot /></main>
  </div>
{:else}
  <Login />
{/if}
