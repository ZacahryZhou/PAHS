CREATE TABLE IF NOT EXISTS runs (
  run_id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL DEFAULT 'default',
  status TEXT NOT NULL,
  orchestrator_profile TEXT,
  origin_channel TEXT NOT NULL DEFAULT 'cli',
  current_milestone_id TEXT,
  command TEXT NOT NULL,
  plan_json TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS review_queue (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id TEXT NOT NULL,
  milestone_id TEXT,
  review_type TEXT NOT NULL,
  payload_json TEXT,
  status TEXT NOT NULL DEFAULT 'pending',
  presented_at TEXT NOT NULL,
  resolved_at TEXT,
  resolved_via_channel TEXT,
  FOREIGN KEY (run_id) REFERENCES runs(run_id)
);

CREATE TABLE IF NOT EXISTS user_channels (
  user_id TEXT NOT NULL,
  channel TEXT NOT NULL,
  channel_user_id TEXT NOT NULL,
  PRIMARY KEY (channel, channel_user_id)
);

CREATE INDEX IF NOT EXISTS idx_review_queue_status ON review_queue(status);
CREATE INDEX IF NOT EXISTS idx_runs_status ON runs(status);
