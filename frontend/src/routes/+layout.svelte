<script lang="ts">
  import "../app.css";
  import { onMount } from "svelte";
  import { page } from "$app/stores";
  import { auth, logout } from "$lib/auth";
  import { goto } from "$app/navigation";
  import { api } from "$lib/api/client";
  import Login from "$lib/components/Login.svelte";

  const nav = [
    { href: "/", label: "Dashboard", icon: "▪" },
    { href: "/parts", label: "Artikel", icon: "◈" },
    { href: "/bom", label: "Stücklisten", icon: "≣" },
    { href: "/changes", label: "Änderungen", icon: "⇄" },
    { href: "/confirmations", label: "Bestätigungen", icon: "✓", badge: true },
    { href: "/reports", label: "Reports", icon: "○" },
    { href: "/documents", label: "Dokumente", icon: "🗎" },
    { href: "/agent", label: "Agent", icon: "✦" },
    { href: "/logs", label: "Logs", icon: "≣" },
    { href: "/admin", label: "Admin", icon: "⚙", adminOnly: true },
  ];

  let openConfirmations = 0;

  function isActive(href: string): boolean {
    const p = $page.url.pathname;
    if (href === "/") return p === "/";
    return p === href || p.startsWith(href + "/");
  }

  async function refreshStats(): Promise<void> {
    if (!$auth.token) return;
    try {
      const s = await api.stats();
      openConfirmations = s.open_confirmations;
    } catch {
      /* ignore */
    }
  }

  async function doLogout(): Promise<void> {
    try {
      await api.logout();
    } catch {
      /* token may already be invalid — clear locally anyway */
    }
    logout();
    goto("/");
  }

  onMount(() => {
    refreshStats();
    const t = setInterval(refreshStats, 30000);
    return () => clearInterval(t);
  });
</script>

{#if $auth.token}
  <div class="shell">
    <aside class="sidebar">
      <div class="logo"><span class="logo-mark">P</span> PLM&nbsp;Studio</div>
      <nav>
        {#each nav as n}
          {#if !n.adminOnly || $auth.role === "admin"}
            <a href={n.href} class:active={isActive(n.href)}>
              <span class="ico">{n.icon}</span>{n.label}
              {#if n.badge && openConfirmations > 0}<span class="nav-badge">{openConfirmations}</span>{/if}
            </a>
          {/if}
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
