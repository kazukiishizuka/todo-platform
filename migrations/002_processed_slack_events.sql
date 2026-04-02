CREATE TABLE processed_slack_events (
  id UUID PRIMARY KEY,
  event_id TEXT NOT NULL UNIQUE,
  created_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX idx_processed_slack_events_event_id ON processed_slack_events(event_id);
