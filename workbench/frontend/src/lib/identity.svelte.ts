/** Who is signed in, for the whole app. The backend's role checks are the
 * ones that count; this only hides what the person cannot do. */

export type Role = "planner" | "approver";

export interface Identity {
  name: string;
  email: string;
  roles: Role[];
  id: string;
}

export const session = $state<{ identity: Identity | null; mode: "oidc" | "local" }>({ identity: null, mode: "local" });

/** Whether the signed-in person holds role. */
export function can(role: Role): boolean {
  return session.identity?.roles.includes(role) ?? false;
}

/** The sign-in errors the backend redirects back with. */
export const SIGN_IN_ERRORS: Record<string, string> = {
  unverified: "The sign-in could not be verified. Try again.",
  expired: "The sign-in took too long. Try again.",
  no_role: "You have no role in the plan workbench. Ask to be added to its planner or approver group.",
  provider_refused: "The identity provider did not sign you in.",
};
