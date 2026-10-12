/** Turns the broker's viewer events into a chat transcript. */
import type { GraphNode } from "./types";

export interface BrokerEvent {
  seq: number;
  time: string;
  type: "state" | "update" | "permission" | "permission_resolved" | "result" | "error";
  update?: { sessionId?: string; update?: Record<string, unknown> };
  id?: string;
  request?: { toolCall?: { title?: string; toolCallId?: string; kind?: string }; options?: PermissionOption[] };
  message?: string;
  floor?: string;
  driverTurn?: string;
  op?: string;
}

export interface PermissionOption {
  optionId: string;
  name: string;
  kind: string;
}

export type ChatItem =
  | { kind: "agent"; key: string; text: string; time: number }
  | { kind: "thought"; key: string; text: string; time: number }
  | { kind: "user"; key: string; text: string; time: number }
  | { kind: "tool"; key: string; title: string; status: string; time: number }
  | { kind: "permission"; key: string; id: string; title: string; options: PermissionOption[]; resolved: string | null; time: number }
  | { kind: "notice"; key: string; text: string; time: number };

export interface Transcript {
  items: ChatItem[];
  busy: boolean;
  lastSeq: number;
}

export function emptyTranscript(): Transcript {
  return { items: [], busy: false, lastSeq: 0 };
}

const t = (iso: string | number) => (typeof iso === "number" ? iso * 1000 : Date.parse(iso) || Date.now());

function text(content: unknown): string {
  if (content && typeof content === "object" && "text" in content) return String((content as { text: unknown }).text ?? "");
  return "";
}

/** Apply one broker event. Consecutive chunks of one kind join into one item. */
export function applyEvent(tr: Transcript, ev: BrokerEvent): Transcript {
  if (ev.seq > 0 && ev.seq <= tr.lastSeq) return tr; // replayed twice
  const items = [...tr.items];
  const last = items[items.length - 1];
  const at = t(ev.time);
  let busy = tr.busy;

  switch (ev.type) {
    case "state":
      busy = ev.driverTurn === "active" || busy;
      break;
    case "update": {
      const u = ev.update?.update ?? {};
      const kind = u.sessionUpdate as string | undefined;
      if (kind === "agent_message_chunk" || kind === "agent_thought_chunk" || kind === "user_message_chunk") {
        const itemKind = kind === "agent_message_chunk" ? "agent" : kind === "agent_thought_chunk" ? "thought" : "user";
        const chunk = text(u.content);
        if (last && last.kind === itemKind) items[items.length - 1] = { ...last, text: last.text + chunk };
        else items.push({ kind: itemKind, key: `e${ev.seq}`, text: chunk, time: at });
        busy = true;
      } else if (kind === "tool_call" || kind === "tool_call_update") {
        const id = String(u.toolCallId ?? ev.seq);
        const idx = items.findIndex((i) => i.kind === "tool" && i.key === `tool-${id}`);
        const status = String(u.status ?? (kind === "tool_call" ? "pending" : "updated"));
        if (idx >= 0) {
          const prev = items[idx] as Extract<ChatItem, { kind: "tool" }>;
          items[idx] = { ...prev, status, title: (u.title as string) ?? prev.title };
        } else {
          items.push({ kind: "tool", key: `tool-${id}`, title: String(u.title ?? "tool call"), status, time: at });
        }
      }
      break;
    }
    case "permission":
      items.push({
        kind: "permission", key: `perm-${ev.id}-${ev.seq}`, id: ev.id ?? "",
        title: ev.request?.toolCall?.title ?? "The agent asks for permission",
        options: ev.request?.options ?? [], resolved: null, time: at,
      });
      break;
    case "permission_resolved": {
      for (let i = items.length - 1; i >= 0; i--) {
        const it = items[i];
        if (it.kind === "permission" && it.id === ev.id && !it.resolved) {
          items[i] = { ...it, resolved: ev.message ?? "answered" };
          break;
        }
      }
      break;
    }
    case "result":
      busy = false;
      break;
    case "error":
      if (ev.message) items.push({ kind: "notice", key: `e${ev.seq}-${items.length}`, text: ev.message, time: at });
      break;
  }
  return { items, busy, lastSeq: Math.max(tr.lastSeq, ev.seq) };
}

/** The person's own messages, which the backend keeps, placed in time order. */
export function withUserMessages(items: ChatItem[], messages: { time: number; text: string }[]): ChatItem[] {
  const users: ChatItem[] = messages.map((m, i) => ({ kind: "user", key: `u${i}`, text: displayText(m.text), time: m.time * 1000 }));
  return [...items, ...users].sort((a, b) => a.time - b.time);
}

const SELECTION_HEADER = "[Selected in the plan graph]";

/** The structured block that tells the agent which nodes the person points at. */
export function selectionBlock(nodes: GraphNode[]): string {
  if (!nodes.length) return "";
  const lines = nodes.map((n) => {
    const tracker = n.tracker ? `, ${n.tracker.identifier}` : "";
    return `- ${n.plan_key} — "${n.title}" (${n.kind}${tracker})`;
  });
  return `${SELECTION_HEADER}\n${lines.join("\n")}\n\n`;
}

export function composeMessage(text: string, attached: GraphNode[]): string {
  return selectionBlock(attached) + text.trim();
}

/** A sent message as the chat shows it: the selection block as a short note. */
export function displayText(sent: string): string {
  if (!sent.startsWith(SELECTION_HEADER)) return sent;
  const [block, ...rest] = sent.split("\n\n");
  const keys = block.split("\n").slice(1).map((l) => l.replace(/^- (\S+).*$/, "$1"));
  return `(about ${keys.join(", ")}) ${rest.join("\n\n")}`;
}
