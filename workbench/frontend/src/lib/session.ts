/** The planning session as the chat pane uses it; tests substitute a fake. */
import { api, type ConfigCategory, type SessionConfig, type SessionStatus } from "./api";
import type { BrokerEvent } from "./chat";

export interface SessionClient {
  status(): Promise<SessionStatus & { messages?: { time: number; text: string }[] }>;
  /** Start a session whose first turn is the person's first message. */
  start(message: string): Promise<SessionStatus>;
  stop(): Promise<SessionStatus>;
  command(cmd: Record<string, unknown>): Promise<unknown>;
  subscribe(onEvent: (e: BrokerEvent) => void, onDown: () => void): () => void;
  config(): Promise<SessionConfig>;
  setConfig(category: ConfigCategory, value: string): Promise<SessionConfig>;
}

export const httpSession: SessionClient = {
  status: () => api.session(),
  start: (message) => api.startSession(message),
  stop: () => api.stopSession(),
  command: (cmd) => api.command(cmd),
  config: () => api.sessionConfig(),
  setConfig: (category, value) => api.setSessionConfig(category, value),
  subscribe(onEvent, onDown) {
    // EventSource sends Last-Event-ID itself when it reconnects, so the
    // broker replays only what this tab missed.
    const es = new EventSource("/api/session/events", { withCredentials: true });
    es.onmessage = (e) => onEvent(JSON.parse(e.data));
    es.onerror = () => {
      if (es.readyState === EventSource.CLOSED) onDown();
    };
    return () => es.close();
  },
};
