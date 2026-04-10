# TODO Platform Handoff

最終更新: 2026-04-10  
対象リポジトリ: [C:\Users\kazuk\OneDrive\ドキュメント\Playground\todo-platform](C:\Users\kazuk\OneDrive\ドキュメント\Playground\todo-platform)  
公開URL: `https://todo-platform-ittk.onrender.com`  
GitHub: [kazukiishizuka/todo-platform](https://github.com/kazukiishizuka/todo-platform)  
最新反映コミットの目安: `c56c5c5`

## 1. このドキュメントの目的

この文書は、次の AI / 開発者が現在の実装状態をすばやく把握し、そのまま保守・拡張を継続できるようにするための handoff である。

対象範囲:
- 仕様の要約
- 実装済み機能
- 現在の運用構成
- 既知の課題
- 重要な設計判断
- 次に着手しやすい作業候補

## 2. プロダクト概要

自然文チャットからタスク/予定を管理するシステム。  
正本はアプリ側 DB。Google Calendar は外部同期先、Slack は通知・会話 UI として使う。

主なユースケース:
- `明日15時に歯医者`
- `明日のタスク教えて`
- `歯医者消して`
- `それ16時にして`
- `引っ越し準備`
- `バックログ見せて`

## 3. 基本方針

- DB 正本
- Slack / Google は外部チャネル
- 曖昧入力は勝手に確定しない
- 原文を保存
- 時刻処理は timezone 前提
- 失敗しても task 自体は失わない
- Google/Slack の成否で主処理を巻き戻さない

## 4. 現在のアーキテクチャ

### 4.1 バックエンド

- FastAPI
- SQLAlchemy
- PostgreSQL 互換運用想定
- Render Web Service + Cron + Postgres

主要責務:
- `app/services/parser.py`
  - 自然文解析
- `app/services/task_service.py`
  - task 正本管理
- `app/services/google_sync.py`
  - Google sync job の投入/実行
- `app/services/slack_service.py`
  - Slack 返信生成、ボタン応答
- `app/workers/job_worker.py`
  - Slack / Google job 実行
- `app/workers/reminder_worker.py`
  - reminder rule 実行

### 4.2 外部連携

- Slack App
  - Events API
  - Interactivity
  - OAuth
- Google Calendar API
  - OAuth
  - event create/update/delete

## 5. デプロイ構成

Render 上に以下を作成済み:
- Web Service: `todo-platform`
- Cron Job: `todo-platform-jobs`
- Cron Job: `todo-platform-reminders`
- Postgres: `todo-platform-db`

### 5.1 重要 URL

Slack:
- Events: `https://todo-platform-ittk.onrender.com/slack/events`
- Interactivity: `https://todo-platform-ittk.onrender.com/slack/interactions`
- OAuth callback: `https://todo-platform-ittk.onrender.com/auth/slack/callback`

Google:
- OAuth callback: `https://todo-platform-ittk.onrender.com/auth/google/callback`

Health:
- `https://todo-platform-ittk.onrender.com/health`

## 6. 環境変数

主要キー:
- `TODO_BASE_URL`
- `TODO_INTERNAL_TOKEN`
- `TODO_DATABASE_URL`
- `TODO_DEFAULT_TIMEZONE`
- `TODO_GOOGLE_CLIENT_ID`
- `TODO_GOOGLE_CLIENT_SECRET`
- `TODO_GOOGLE_REDIRECT_URI`
- `TODO_GOOGLE_CALENDAR_ID`
- `TODO_SLACK_CLIENT_ID`
- `TODO_SLACK_CLIENT_SECRET`
- `TODO_SLACK_REDIRECT_URI`
- `TODO_SLACK_BOT_TOKEN`
- `TODO_SLACK_SIGNING_SECRET`
- `TODO_SLACK_BOT_USER_ID`

注意:
- この会話中で一部 secret は一度露出しているため、本番運用前にはローテーション推奨
- 特に rotate 推奨:
  - Slack bot token
  - Slack signing secret
  - Slack client secret
  - Google client secret

## 7. 実装済み機能

### 7.1 自然文登録

対応例:
- `4月5日15時に面談`
- `明日の15:00に歯医者`
- `来週金曜15時に会議`
- `毎週月曜10時にゼミ`

パーサ対応:
- 明示日付
- 相対日付
- 時刻
- recurrence の一部
- 曖昧性フラグ

### 7.2 照会

対応:
- 今日
- 明日
- 今週
- 今月
- 未完了
- 完了済み
- 期限切れ
- バックログ

Slack 表示仕様:
- 時刻あり: `04/03 11:00 ミーティング`
- due_date のみ: `04/03 レポート提出`
- 日時なし: `期限未設定 引っ越し準備`

### 7.3 更新 / 完了 / 削除

対応:
- `それ16時にして`
- `レポート完了`
- `歯医者消して`

削除は論理削除:
- `deleted_at` を設定
- Google 同期対象なら delete job を積む

### 7.4 中長期タスク

現在は DB カラム追加ではなく、既存フィールドから task type を推定している。

推定ルール:
- `start_datetime` あり -> `event`
- `due_date` のみ -> `deadline_task`
- どちらもなし -> `backlog_task`

日時なしでも、タイトルが明確で曖昧フラグがない場合は保存される。

例:
- `引っ越し準備`
- `新規事業案を考える`

### 7.5 Slack ボタン

ボタン:
- 完了
- 延期
- 削除
- 詳細

現在の仕様:
- 新規登録返信にはボタンあり
- 照会返信にはボタンなし
- 操作結果返信にもボタンなし
- ボタン押下時は `ephemeral` で押下者へ結果表示

### 7.6 重複対策

実装済み:
- Slack `event_id` による events 二重処理防止
- `app_mention` と `message.*` の二重処理防止
- 同一 Slack 投稿の短時間二重送信防止
- 一覧表示時の重複行除去
- 削除時、見えない accidental duplicate をまとめて削除

## 8. 重要な既知の設計判断

### 8.1 DB スキーマ変更を抑えている

Render 上では SQLAlchemy の `Base.metadata.create_all()` で新規 table は作れるが、既存 table の `ALTER` は自動で行われない。

そのため最近の対応では:
- `task_type` のような新概念は DB カラム追加せず推定で運用

これは安全のための判断。  
今後 Alembic を入れて migrations をちゃんと管理するなら、この制約は緩和できる。

### 8.2 query 時は見た目を優先して dedupe

照会では、過去の事故由来の完全重複を 1 件に丸めている。  
ただし DB には duplicate が残っている場合がある。

### 8.3 削除は安全優先

文脈指示:
- `それ`
- `さっき`
- `今日のやつ`

このときだけ context fallback を使う。  
明示指定:
- `歯医者消して`
- `ミーティング完了`

これらでは別タスクへ勝手に fallback しない。

## 9. 重要なファイル

API:
- [C:\Users\kazuk\OneDrive\ドキュメント\Playground\todo-platform\app\main.py](C:\Users\kazuk\OneDrive\ドキュメント\Playground\todo-platform\app\main.py)
- [C:\Users\kazuk\OneDrive\ドキュメント\Playground\todo-platform\app\api\routes\tasks.py](C:\Users\kazuk\OneDrive\ドキュメント\Playground\todo-platform\app\api\routes\tasks.py)
- [C:\Users\kazuk\OneDrive\ドキュメント\Playground\todo-platform\app\api\routes\slack.py](C:\Users\kazuk\OneDrive\ドキュメント\Playground\todo-platform\app\api\routes\slack.py)
- [C:\Users\kazuk\OneDrive\ドキュメント\Playground\todo-platform\app\api\routes\auth.py](C:\Users\kazuk\OneDrive\ドキュメント\Playground\todo-platform\app\api\routes\auth.py)
- [C:\Users\kazuk\OneDrive\ドキュメント\Playground\todo-platform\app\api\routes\internal.py](C:\Users\kazuk\OneDrive\ドキュメント\Playground\todo-platform\app\api\routes\internal.py)

サービス:
- [C:\Users\kazuk\OneDrive\ドキュメント\Playground\todo-platform\app\services\parser.py](C:\Users\kazuk\OneDrive\ドキュメント\Playground\todo-platform\app\services\parser.py)
- [C:\Users\kazuk\OneDrive\ドキュメント\Playground\todo-platform\app\services\task_service.py](C:\Users\kazuk\OneDrive\ドキュメント\Playground\todo-platform\app\services\task_service.py)
- [C:\Users\kazuk\OneDrive\ドキュメント\Playground\todo-platform\app\services\slack_service.py](C:\Users\kazuk\OneDrive\ドキュメント\Playground\todo-platform\app\services\slack_service.py)
- [C:\Users\kazuk\OneDrive\ドキュメント\Playground\todo-platform\app\services\slack_client.py](C:\Users\kazuk\OneDrive\ドキュメント\Playground\todo-platform\app\services\slack_client.py)
- [C:\Users\kazuk\OneDrive\ドキュメント\Playground\todo-platform\app\services\google_sync.py](C:\Users\kazuk\OneDrive\ドキュメント\Playground\todo-platform\app\services\google_sync.py)

リポジトリ:
- [C:\Users\kazuk\OneDrive\ドキュメント\Playground\todo-platform\app\repositories\memory.py](C:\Users\kazuk\OneDrive\ドキュメント\Playground\todo-platform\app\repositories\memory.py)
- [C:\Users\kazuk\OneDrive\ドキュメント\Playground\todo-platform\app\repositories\sqlalchemy_repo.py](C:\Users\kazuk\OneDrive\ドキュメント\Playground\todo-platform\app\repositories\sqlalchemy_repo.py)

ワーカー:
- [C:\Users\kazuk\OneDrive\ドキュメント\Playground\todo-platform\app\workers\job_worker.py](C:\Users\kazuk\OneDrive\ドキュメント\Playground\todo-platform\app\workers\job_worker.py)
- [C:\Users\kazuk\OneDrive\ドキュメント\Playground\todo-platform\app\workers\reminder_worker.py](C:\Users\kazuk\OneDrive\ドキュメント\Playground\todo-platform\app\workers\reminder_worker.py)

テスト:
- [C:\Users\kazuk\OneDrive\ドキュメント\Playground\todo-platform\tests\test_parser.py](C:\Users\kazuk\OneDrive\ドキュメント\Playground\todo-platform\tests\test_parser.py)
- [C:\Users\kazuk\OneDrive\ドキュメント\Playground\todo-platform\tests\test_task_service.py](C:\Users\kazuk\OneDrive\ドキュメント\Playground\todo-platform\tests\test_task_service.py)
- [C:\Users\kazuk\OneDrive\ドキュメント\Playground\todo-platform\tests\test_external_services.py](C:\Users\kazuk\OneDrive\ドキュメント\Playground\todo-platform\tests\test_external_services.py)
- [C:\Users\kazuk\OneDrive\ドキュメント\Playground\todo-platform\tests\test_workers.py](C:\Users\kazuk\OneDrive\ドキュメント\Playground\todo-platform\tests\test_workers.py)

## 10. テスト実行方法

ローカル:

```powershell
python -m unittest discover -s tests -v
```

2026-04-10 時点の通過数:
- 31 tests passed

## 11. 最近直した主要バグ

### 11.1 Slack 署名検証失敗
- secret 末尾改行
- `.strip()` で吸収

### 11.2 Render Cron の URL / token 改行
- `TODO_BASE_URL`
- `TODO_INTERNAL_TOKEN`
- `.strip()` で吸収

### 11.3 `app_mention` 未処理
- `message` だけ見ていたため無反応
- `app_mention` を処理追加

### 11.4 Slack 二重返信
- `app_mention` と `message.*` の重複
- `event_id` dedupe
- same mention message 無視
- recent post dedupe

### 11.5 query にボタンが出る
- 照会系は `blocks=[]` に固定

### 11.6 操作結果にボタンが出る
- delete / complete / update 返答は text only

### 11.7 明示削除が文脈 fallback で別 task を消す
- 明示指定時は context fallback 禁止

### 11.8 hidden duplicate が削除できない
- 同一 signature の duplicate はまとめて削除

## 12. 現在の既知課題

### 12.1 削除取り消しがない

論理削除はしているが、ユーザー向けに restore 操作がまだない。  
誤削除対応として次の候補に入れる価値が高い。

### 12.2 confirmation UX がまだ弱い

複数候補提示は仕様にあるが、現状は単純な `特定できませんでした` に寄る箇所が残る。

### 12.3 Google OAuth 接続後の本番挙動は要再確認

Slack 側の疎通はかなり進んでいるが、Google 連携は環境差分を含めて改めて end-to-end 確認したい。

### 12.4 本格 migration 管理がない

将来的には Alembic 導入推奨。

## 13. 次に着手しやすい候補

優先度高:
1. `削除取り消し` / `最近削除したタスクを戻す`
2. 複数候補の確認 UI を Block Kit で実装
3. Google 連携の end-to-end 検証

優先度中:
1. `priority`
2. `tag`
3. `project`
4. `backlog / today / scheduled` の見やすい一覧整形

優先度高だが設計系:
1. Alembic 導入
2. migration 方針の確立
3. 操作ログの整理

## 14. AI への引き継ぎメモ

次の AI は以下をまず確認するとよい。

1. GitHub の最新 main が Render に反映されているか
2. `slack_service.py` が UTF-8 の正常文言でデプロイされているか
3. `/health` が OK か
4. Slack で以下を確認:
   - `明日のタスク教えて`
   - `歯医者消して`
   - ボタン `完了 / 削除 / 延期`
5. DB に古い duplicate が残っていないか必要に応じて確認

最低限の sanity check 発話:

```text
@Todo管理くん 明日のタスク教えて
@Todo管理くん 歯医者消して
@Todo管理くん 引っ越し準備
@Todo管理くん バックログ見せて
```

## 15. 結論

このプロジェクトは「自然文 task manager + Slack bot + Google Calendar sync」として、初版としてかなり形になっている。  
特に以下はすでに実用レベルに近い:

- Slack 自然文登録
- Slack 照会
- 基本的な更新 / 完了 / 削除
- ボタン UI
- 重複対策
- 中長期タスク保持

残作業は「UXの磨き込み」と「本番運用向けの堅牢化」が中心である。
