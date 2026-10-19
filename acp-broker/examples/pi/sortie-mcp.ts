// Registers the MCP servers Sortie wrote for this session in
// <workspace>/.sortie/mcp.json, so Sortie's tools reach pi without project
// trust and without touching the user's pi configuration.
import { readFileSync } from "node:fs";
import { join } from "node:path";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

export default function (pi: ExtensionAPI) {
  const path = process.env.SORTIE_MCP_CONFIG ?? join(process.cwd(), ".sortie", "mcp.json");
  let servers: Record<string, any> = {};
  try {
    servers = JSON.parse(readFileSync(path, "utf8")).mcpServers ?? {};
  } catch {
    return; // Not a Sortie workspace, or no servers for this session.
  }
  for (const [name, config] of Object.entries(servers)) {
    // Sortie's tool set is small and the agent should see it without
    // searching, so declare it directly unless the config says otherwise.
    pi.registerMcpServer(name, { exposure: "direct", ...config });
  }
}
