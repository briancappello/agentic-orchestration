-- One row per project: a spec store paired with one tracker project.
CREATE TABLE projects (
  id            INTEGER PRIMARY KEY,
  slug          TEXT NOT NULL UNIQUE
                CHECK (length(slug) BETWEEN 1 AND 48
                       AND slug GLOB '[a-z0-9]*'
                       AND slug NOT GLOB '*[^a-z0-9-]*'),
  name          TEXT NOT NULL CHECK (length(trim(name)) > 0),
  huly_project  TEXT NOT NULL UNIQUE,
  store_path    TEXT NOT NULL UNIQUE,
  created_at    INTEGER NOT NULL
);
