# TODO Management Platform

自然文入力を正本DBに保存し、Google Calendar 同期と Slack Bot 応答を統合するバックエンドです。

## System Diagram

```mermaid
flowchart LR
  User["Chat / Slack User"] --> API["FastAPI"]
  API --> Parser["Natural Language Parser"]
  API --> TaskService["Task Service"]
  TaskService --> DB[("PostgreSQL")]
  TaskService --> Context["Conversation Context"]
  TaskService --> JobQueue[("Job Queue Table")]
  API --> GoogleOAuth["Google OAuth"]
  API --> SlackEvents["Slack Events / Interactions"]
  JobQueue --> Worker["Job Worker"]
  Worker --> GoogleSync["Google Calendar API"]
  Worker --> SlackWebAPI["Slack Web API"]
  Scheduler["Reminder Worker"] --> JobQueue
```

## Directory Layout

- `app/main.py`: FastAPI entrypoint
- `app/models.py`: SQLAlchemy models
- `app/repositories/sqlalchemy_repo.py`: PostgreSQL repository
- `app/repositories/memory.py`: fallback repository for lightweight tests
- `app/services/parser.py`: rule-based natural language parsing
- `app/services/task_service.py`: task use cases and context resolution
- `app/services/google_auth.py`: Google OAuth code exchange
- `app/services/google_calendar_client.py`: Calendar API adapter
- `app/services/google_sync.py`: sync queue and execution
- `app/services/slack_client.py`: Slack signature verification and postMessage adapter
- `app/services/slack_service.py`: Slack conversational operations
- `app/workers/reminder_worker.py`: reminder scheduler
- `app/workers/job_worker.py`: queued job executor
- `migrations/001_initial_schema.sql`: initial PostgreSQL schema
- `docker-compose.yml`: local PostgreSQL / Redis bootstrapping

## Main Capabilities

- 自然文による登録、照会、更新、削除、完了
- 曖昧入力の `confirmed / needs_confirmation / on_hold` 判定
- 会話文脈による `それ16時にして` 解決
- Google OAuth と Calendar 同期ジョブ処理
- Slack private channel 向け Events / Interactions / postMessage
- DB正本と非同期ジョブ分離による外部API障害耐性
- parse / sync / slack message / context / job queue の保存

## Environment Variables

`.env.example` を元に設定します。

- `TODO_DATABASE_URL`: 例 `postgresql+psycopg://postgres:postgres@localhost:5432/todo_platform`
- `TODO_GOOGLE_CLIENT_ID`
- `TODO_GOOGLE_CLIENT_SECRET`
- `TODO_GOOGLE_REDIRECT_URI`
- `TODO_SLACK_CLIENT_ID`
- `TODO_SLACK_CLIENT_SECRET`
- `TODO_SLACK_REDIRECT_URI`
- `TODO_SLACK_BOT_TOKEN`
- `TODO_SLACK_SIGNING_SECRET`
- `TODO_SLACK_BOT_USER_ID`
- `TODO_INTERNAL_TOKEN`

## Local Run

1. `docker compose up -d`
2. `.env.example` を `.env` として配置して値を設定
3. 依存導入: `python -m pip install -e .`
4. API 起動: `uvicorn app.main:app --reload`

## Main Endpoints

- `POST /tasks/parse-and-create`
- `GET /tasks`
- `PATCH /tasks/{taskId}`
- `POST /tasks/{taskId}/complete`
- `DELETE /tasks/{taskId}`
- `GET /auth/google/start?userId=...`
- `GET /auth/google/callback`
- `GET /auth/slack/start?userId=...`
- `GET /auth/slack/callback`
- `POST /slack/events`
- `POST /slack/interactions`
- `POST /reminder-rules`
- `POST /internal/jobs/run`
- `POST /internal/reminders/run`

## Notes

- DB正本を守るため、外部同期失敗は task 作成失敗にしません。
- Google / Slack 送信はジョブ化して再試行しやすくしています。
- 初版パーサはルールベース中心です。複雑な曖昧表現は確認フローに回します。
- 現在のジョブキューは DB テーブルベースです。将来的に Redis/BullMQ 相当へ差し替えやすい構成です。
- Slack OAuth redirect URL は HTTPS が必要です。ローカル確認では `ngrok` などの HTTPS トンネルを使います。
- `/internal/*` エンドポイントは `X-Internal-Token` ヘッダーで保護します。
