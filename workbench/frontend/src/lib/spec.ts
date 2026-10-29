/** The requirements a story covers, read from its change's delta specs. */
import { projectPath } from "./api";

export interface ScenarioStep { keyword: string; text: string }
export interface Scenario { name: string; steps: ScenarioStep[] }
export interface Requirement { name: string; operation: string; text: string; scenarios: Scenario[] }
/** Each capability of a change, with its added and modified requirements in file order. */
export type ChangeRequirements = Record<string, Requirement[]>;

export interface SpecReader {
  requirements(change: string): Promise<ChangeRequirements>;
}

export function httpSpecs(slug: string): SpecReader {
  return {
    async requirements(change) {
      const r = await fetch(`${projectPath(slug)}/changes/${encodeURIComponent(change)}/requirements`, { credentials: "same-origin" });
      if (!r.ok) throw new Error(`The specs of ${change} could not be read (${r.status}).`);
      return ((await r.json()) as { capabilities: ChangeRequirements }).capabilities;
    },
  };
}

export interface CoveredRequirement {
  ref: string;
  name: string;
  /** Null while the specs load, or when the change has no such requirement. */
  requirement: Requirement | null;
}

/** A story's `covers` refs grouped by capability, in the order the story lists them. */
export function groupCovers(covers: string[], loaded: ChangeRequirements | null): { capability: string; items: CoveredRequirement[] }[] {
  const groups = new Map<string, CoveredRequirement[]>();
  for (const ref of covers) {
    const at = ref.indexOf("#");
    const capability = at < 0 ? ref : ref.slice(0, at);
    const name = at < 0 ? "" : ref.slice(at + 1);
    const requirement = loaded?.[capability]?.find((r) => r.name === name) ?? null;
    if (!groups.has(capability)) groups.set(capability, []);
    groups.get(capability)!.push({ ref, name, requirement });
  }
  return [...groups].map(([capability, items]) => ({ capability, items }));
}
