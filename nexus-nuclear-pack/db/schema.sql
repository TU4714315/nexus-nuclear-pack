-- SQLite schema for Evidence Ledger (v0.1)
CREATE TABLE IF NOT EXISTS runs (
  run_id TEXT PRIMARY KEY,
  started_at_utc TEXT NOT NULL,
  finished_at_utc TEXT,
  budget_json TEXT NOT NULL,
  policy_hash TEXT NOT NULL,
  goal TEXT NOT NULL,
  status TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS evidence (
  evidence_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  ts_utc TEXT NOT NULL,
  capability TEXT NOT NULL,
  provider TEXT NOT NULL,
  summary TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  sha256 TEXT NOT NULL,
  cost_json TEXT NOT NULL,
  FOREIGN KEY(run_id) REFERENCES runs(run_id)
);

CREATE TABLE IF NOT EXISTS candidates (
  candidate_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  kind TEXT NOT NULL,
  value TEXT NOT NULL,
  confidence REAL NOT NULL,
  reason TEXT NOT NULL,
  FOREIGN KEY(run_id) REFERENCES runs(run_id)
);
