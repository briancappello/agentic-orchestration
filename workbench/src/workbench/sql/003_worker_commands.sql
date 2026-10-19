-- The commands people sent to the agents Sortie runs, and who sent them.
CREATE TABLE worker_commands (
  id           INTEGER PRIMARY KEY,
  project_id   INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  identifier   TEXT NOT NULL,
  session_id   TEXT,
  op           TEXT NOT NULL,
  text         TEXT,
  actor_id     TEXT NOT NULL,
  actor_name   TEXT NOT NULL,
  created_at   REAL NOT NULL
);
CREATE INDEX worker_commands_story ON worker_commands (project_id, identifier, created_at);
