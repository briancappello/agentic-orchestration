-- What a person approved, per story. The planning agent writes the spec
-- store, never this database, so it cannot approve its own work.
CREATE TABLE approvals (
  project_id     INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  plan_key       TEXT NOT NULL,
  digest         TEXT NOT NULL,
  approver_id    TEXT NOT NULL,
  approver_name  TEXT NOT NULL,
  approved_at    INTEGER NOT NULL,
  PRIMARY KEY (project_id, plan_key)
);

-- Stories that need a person again, and why: a cancelled blocker, for one.
CREATE TABLE rereviews (
  project_id  INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  plan_key    TEXT NOT NULL,
  reason      TEXT NOT NULL,
  ref         TEXT NOT NULL DEFAULT '',
  created_at  INTEGER NOT NULL,
  PRIMARY KEY (project_id, plan_key)
);
