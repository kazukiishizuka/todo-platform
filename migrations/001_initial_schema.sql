CREATE TABLE tasks (
  id UUID PRIMARY KEY,
  user_id UUID NOT NULL,
  title TEXT NOT NULL,
  description TEXT,
  original_text TEXT NOT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'pending',
  priority VARCHAR(32),
  due_date DATE,
  start_datetime TIMESTAMPTZ,
  end_datetime TIMESTAMPTZ,
  timezone VARCHAR(64) NOT NULL,
  is_all_day BOOLEAN NOT NULL DEFAULT FALSE,
  recurrence_rule TEXT,
  parser_confidence DECIMAL(5,4),
  parse_status VARCHAR(32),
  google_event_id TEXT,
  google_sync_status VARCHAR(32),
  sync_retry_count INT NOT NULL DEFAULT 0,
  last_sync_error TEXT,
  completed_at TIMESTAMPTZ,
  deleted_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX idx_tasks_user_id ON tasks(user_id);
CREATE INDEX idx_tasks_status ON tasks(status);
CREATE INDEX idx_tasks_due_date ON tasks(due_date);
CREATE INDEX idx_tasks_start_datetime ON tasks(start_datetime);

CREATE TABLE task_parse_logs (
  id UUID PRIMARY KEY,
  task_id UUID REFERENCES tasks(id),
  original_text TEXT NOT NULL,
  parsed_json JSONB NOT NULL,
  confidence DECIMAL(5,4),
  ambiguity_flags JSONB,
  created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE task_sync_logs (
  id UUID PRIMARY KEY,
  task_id UUID NOT NULL REFERENCES tasks(id),
  provider VARCHAR(32) NOT NULL,
  operation_type VARCHAR(32) NOT NULL,
  status VARCHAR(32) NOT NULL,
  error_message TEXT,
  payload_json JSONB,
  created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE slack_connections (
  id UUID PRIMARY KEY,
  user_id UUID NOT NULL,
  slack_workspace_id TEXT NOT NULL,
  slack_user_id TEXT NOT NULL,
  slack_team_name TEXT,
  bot_user_id TEXT,
  bot_access_token TEXT,
  access_scope TEXT,
  connected_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE slack_channels (
  id UUID PRIMARY KEY,
  user_id UUID NOT NULL,
  slack_channel_id TEXT NOT NULL,
  channel_name TEXT,
  is_private BOOLEAN NOT NULL DEFAULT TRUE,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE reminder_rules (
  id UUID PRIMARY KEY,
  user_id UUID NOT NULL,
  slack_channel_id TEXT NOT NULL,
  reminder_type VARCHAR(64) NOT NULL,
  frequency VARCHAR(32) NOT NULL,
  day_of_week VARCHAR(16),
  time_of_day VARCHAR(16) NOT NULL,
  timezone VARCHAR(64) NOT NULL,
  enabled BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE slack_message_logs (
  id UUID PRIMARY KEY,
  user_id UUID NOT NULL,
  slack_channel_id TEXT NOT NULL,
  message_type VARCHAR(64) NOT NULL,
  payload_json JSONB,
  status VARCHAR(32) NOT NULL,
  error_message TEXT,
  sent_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE conversation_contexts (
  id UUID PRIMARY KEY,
  user_id UUID NOT NULL,
  channel_type VARCHAR(32) NOT NULL,
  channel_id TEXT NOT NULL,
  last_referenced_task_ids JSONB,
  context_json JSONB,
  updated_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX idx_context_user_channel ON conversation_contexts(user_id, channel_type, channel_id);

CREATE TABLE google_connections (
  id UUID PRIMARY KEY,
  user_id UUID NOT NULL,
  google_account_email TEXT,
  access_token TEXT NOT NULL,
  refresh_token TEXT,
  token_expiry TIMESTAMPTZ,
  scope TEXT,
  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX idx_google_connections_user_id ON google_connections(user_id);

CREATE TABLE job_queue_items (
  id UUID PRIMARY KEY,
  job_type VARCHAR(64) NOT NULL,
  status VARCHAR(32) NOT NULL,
  payload_json JSONB NOT NULL,
  retry_count INT NOT NULL DEFAULT 0,
  run_after TIMESTAMPTZ,
  last_error TEXT,
  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX idx_job_queue_status ON job_queue_items(status);
CREATE INDEX idx_job_queue_type ON job_queue_items(job_type);
