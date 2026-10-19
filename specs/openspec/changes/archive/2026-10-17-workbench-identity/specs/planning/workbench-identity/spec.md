## Purpose

Tells the plan workbench who each person is and what they may do, using the team's own OpenID Connect provider, so that every action that changes what agents do can name the person who did it.

## ADDED Requirements

### Requirement: Sign in through OpenID Connect
When an issuer is configured, the workbench SHALL sign people in with the OpenID Connect authorization code flow and PKCE. It SHALL find the provider's endpoints and keys through the issuer's discovery document. It SHALL send a fresh `state` and `nonce` with each sign-in, and SHALL refuse a callback whose `state` does not match, whose ID token fails signature, issuer, audience, expiry, or `nonce` checks, or that arrives after the sign-in attempt expired. A refused callback SHALL sign nobody in and SHALL show the reason. After a sign-in, the workbench SHALL return the person to the page they asked for, but only to a path on the workbench itself.

#### Scenario: A person signs in
- **WHEN** a person opens the workbench without a session
- **THEN** the workbench sends them to the provider
- **AND** after they sign in there, they are back on the page they opened, signed in

#### Scenario: A forged callback
- **WHEN** a callback arrives with a `state` that the workbench did not issue
- **THEN** nobody is signed in
- **AND** the page says that the sign-in could not be verified

#### Scenario: A redirect to another site
- **WHEN** a sign-in asks to return to `https://evil.example/`
- **THEN** after sign-in the person lands on the workbench's home page

### Requirement: The session holds the identity
After a sign-in, the workbench SHALL keep the person's identity in its own session: the issuer and subject as the stable key, the display name, the email, and the roles. The browser SHALL hold only the workbench's own session cookie, which SHALL be signed, `HttpOnly`, `SameSite=Strict`, and `Secure` behind HTTPS. No provider token SHALL reach the browser. A session SHALL end after its configured maximum age. A person SHALL be able to sign out, which SHALL end the workbench session.

#### Scenario: No provider token in the browser
- **WHEN** a person is signed in
- **THEN** no response to the browser contains the provider's ID, access, or refresh token

#### Scenario: Who am I
- **WHEN** a signed-in person asks the workbench who they are
- **THEN** the answer holds their name, email, and roles

#### Scenario: Sign out
- **WHEN** a person signs out
- **THEN** their next request is not signed in

### Requirement: Roles from provider claims
The workbench SHALL map one configured claim of the ID token, a list of group names, to two roles:
- `planner`: may sign in, see and edit plans, sync, run planning sessions, and create, rename, and remove projects;
- `approver`: may do everything a `planner` may, and SHALL be the only role allowed to take an action that the specs of other changes reserve for approvers.

The group names for each role SHALL be configuration. Membership in the approver group SHALL grant both roles. A person in neither group SHALL NOT be signed in, and SHALL be told that they have no role. Roles SHALL be read at sign-in, and a change at the provider SHALL apply at the person's next sign-in.

#### Scenario: A planner
- **WHEN** a person's `groups` claim holds the planner group only
- **THEN** their roles are `planner`

#### Scenario: An approver
- **WHEN** a person's `groups` claim holds the approver group
- **THEN** their roles are `planner` and `approver`

#### Scenario: No role
- **WHEN** a person's `groups` claim holds neither group
- **THEN** they are not signed in, and the page says they have no role in the workbench

### Requirement: Routes check the role
Every workbench API route SHALL require a session. A route that needs `approver` SHALL refuse a person without it with `403` and the code `role_required`, and SHALL take no action. The frontend SHALL hide or disable an action the person's roles do not allow, but the backend check SHALL be the one that counts.

#### Scenario: A planner tries an approver action
- **WHEN** a person with only `planner` calls a route that needs `approver`
- **THEN** the workbench answers `403` with `role_required`
- **AND** nothing changes

### Requirement: Actions name the person
The workbench SHALL give every route the signed-in identity: issuer, subject, name, email, and roles. Records that other changes require, such as approvals and steering commands, SHALL take the actor from this identity and never from the request body.

#### Scenario: The actor is not taken from the request
- **WHEN** a request to an approver route carries `"approved_by": "someone-else"` in its body
- **THEN** the record names the signed-in person

### Requirement: Local mode for development
When no issuer is configured, the workbench SHALL keep the password sign-in with a configured password hash, and SHALL treat the person who signs in as a local identity with both roles. The local identity's issuer SHALL be `local`, so that no record made in local mode can be mistaken for a provider identity. The workbench SHALL refuse to start in local mode when its bind address is not loopback, unless local mode is explicitly allowed by configuration.

#### Scenario: Local development
- **WHEN** no issuer is configured and the workbench binds to `127.0.0.1`
- **THEN** a person signs in with the password and has both roles
- **AND** their identity's issuer is `local`

#### Scenario: Local mode exposed
- **WHEN** no issuer is configured and the workbench binds to `0.0.0.0`
- **AND** local mode is not explicitly allowed
- **THEN** the workbench refuses to start and names the missing issuer setting
