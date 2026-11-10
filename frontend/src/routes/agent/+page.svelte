<script lang="ts">
  import { onMount } from "svelte";
  import { agentApi, chatStream, api, type ChatEvent, type Conversation, type ConversationDetail } from "$lib/api/client";

  interface Msg {
    role: "user" | "assistant" | "tool";
    text?: string;
    tool?: string;
    proposalId?: string;
    proposalSummary?: string;
    error?: string;
  }

  let conversations: Conversation[] = [];
  let activeId: string | null = null;
  let messages: Msg[] = [];
  let input = "";
  let sending = false;
  let error = "";
  let eventLog: string[] = [];
  let showEvents = false;

  async function loadConversations(): Promise<void> {
    try {
      conversations = await agentApi.conversations();
    } catch (e: any) {
      error = e?.message ?? "Agent-Service nicht erreichbar (Port 8001?)";
    }
  }

  async function openConversation(id: string): Promise<void> {
    activeId = id;
    error = "";
    try {
      const c: ConversationDetail = await agentApi.conversation(id);
      messages = c.messages
        .filter((m) => m.role === "user" || m.role === "assistant")
        .map((m) => ({ role: m.role as "user" | "assistant", text: (m.content as any)?.text ?? "" }));
    } catch (e: any) {
      error = e?.message;
    }
  }

  function newChat(): void {
    activeId = null;
    messages = [];
  }

  async function send(): Promise<void> {
    const text = input.trim();
    if (!text || sending) return;
    input = "";
    sending = true;
    error = "";
    messages = [...messages, { role: "user", text }];
    const assistantMsg: Msg = { role: "assistant", text: "" };
    messages = [...messages, assistantMsg];
    eventLog = [];
    try {
      await chatStream(text, activeId, (ev: ChatEvent) => {
        eventLog = [...eventLog, JSON.stringify(ev)];
        if (ev.type === "conversation") {
          activeId = ev.conversation_id;
          loadConversations();
        } else if (ev.type === "error") {
          messages = [...messages, { role: "assistant", error: ev.message }];
        } else if (ev.type === "tool_call") {
          const res = ev.result ?? {};
          if (res.proposed) {
            messages = [
              ...messages,
              { role: "tool", tool: ev.name, proposalId: res.confirmation_id, proposalSummary: res.summary },
            ];
          } else {
            messages = [...messages, { role: "tool", tool: `${ev.name} → HTTP ${res.status}` }];
          }
        } else if (ev.type === "delta") {
          assistantMsg.text = (assistantMsg.text ?? "") + ev.content;
          messages = [...messages];
        }
      });
    } catch (e: any) {
      error = e?.message ?? "Chat fehlgeschlagen";
      messages = [...messages, { role: "assistant", error: `Chat fehlgeschlagen: ${error}` }];
    } finally {
      sending = false;
    }
  }

  async function approve(confId: string): Promise<void> {
    error = "";
    try {
      await api.approve(confId);
      messages = messages.map((m) => (m.proposalId === confId ? { ...m, proposalId: undefined, proposalSummary: (m.proposalSummary ?? "") + "  ✓ genehmigt" } : m));
    } catch (e: any) {
      error = e?.message;
    }
  }

  onMount(loadConversations);
</script>

<div class="page-head">
  <div>
    <h1>Agent</h1>
    <div class="tag">KI-Prompt-Schicht — Schreibzugriffe nur als Vorschlag (202), Freigabe hier oder unter Bestätigungen</div>
  </div>
  <button class="btn btn-primary" on:click={newChat}>+ Neuer Chat</button>
</div>

{#if error}<div class="error">{error}</div>{/if}

<div class="chat-layout">
  <div class="card chat-side">
    {#if conversations.length === 0}<div class="empty">Keine Chats.</div>{/if}
    {#each conversations as c}
      <a href="/agent" class:active={c.id === activeId} on:click|preventDefault={() => openConversation(c.id)}>{c.title}</a>
    {/each}
  </div>
  <div class="card">
    <div class="chat-log">
      {#if messages.length === 0}<div class="empty">Stelle eine Frage, z. B. „Suche alle TEST-Teile und lege ‚Neues Teil‘ als Änderungsvorschlag an“.</div>{/if}
      {#each messages as m}
        {#if m.error}
          <div class="msg error">⚠ {m.error}</div>
        {:else if m.role === "tool"}
          <div class="msg tool">
            🔧 {m.tool ?? ""}
            {#if m.proposalId}
              <div class="proposal">
                <span>Vorschlag: {m.proposalSummary}</span>
                <button class="btn btn-primary btn-sm" on:click={() => m.proposalId && approve(m.proposalId)}>Genehmigen</button>
              </div>
            {/if}
          </div>
        {:else}
          <div class="msg {m.role}">{m.text}</div>
        {/if}
      {/each}
      {#if sending}<div class="msg tool">Agent arbeitet …</div>{/if}
    </div>
    {#if eventLog.length > 0}
      <details style="margin-top: 10px">
        <summary class="small muted" on:click={() => (showEvents = !showEvents)}>SSE-Event-Log ({eventLog.length})</summary>
        <pre class="json" style="max-height: 200px">{eventLog.join("\n")}</pre>
      </details>
    {/if}
    <div class="chat-input">
      <input class="input" style="flex: 1" placeholder="Nachricht an den Agenten …" bind:value={input} on:keydown={(e) => e.key === "Enter" && send()} disabled={sending} />
      <button class="btn btn-primary" on:click={send} disabled={sending || !input.trim()}>Senden</button>
    </div>
  </div>
</div>
