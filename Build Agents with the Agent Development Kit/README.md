# Build Agents with the Agent Development Kit ― サンプルコード（M1〜M13）

講師ガイド「Build Agents with the Agent Development Kit 講師ガイド（M1〜M13）」の
**提示コード**を、モジュールごとに 1 つの agent フォルダとして実装したものです。
コース全体を通して同じ「注文サポート agent」が育っていく構成になっています。

- 検証環境：google-adk **2.9.2** / Python 3.13 / google-cloud-aiplatform 1.165.1
- コメントはすべて日本語。tool の docstring は「モデル向けの仕様書」なので英語のままにしています（M1・M4 の説明どおり）。

## セットアップ

```bash
uv sync                                  # google-adk[gcp,mcp]==2.9.2 が入る
cp agents/.env.example agents/.env       # GOOGLE_API_KEY を書き込む
cd agents
uv run adk web .                         # http://localhost:8000 で m01〜m13 を切り替えて試せる
```

読み込みチェック（モデルは呼ばないので API キー不要）：

```bash
uv run python check_samples.py
```

## フォルダ構成

各フォルダの `agent.py` にある `root_agent` が、そのモジュール時点の完成形です。
ほかのファイルは、ガイドの Code N.（素材 N.）を個別に見せるための部品です。

| フォルダ | モジュール | root_agent | ほかのファイル |
| --- | --- | --- | --- |
| `m01_adk` | M1 ADK | 20 行の billing_agent | `__init__.py`（Code 4） |
| `m02_configuring_agent` | M2 Configuring a Simple Agent | 任意パラメータ入り billing_agent（Code 3） | 同じファイルに Code 1 / 2 / 4 |
| `m03_running_agent` | M3 Running Your First Agent | root_agent の命名規約（Code 2） | `run_commands.sh`（Code 1 / 4） |
| `m04_tools` | M4 Building Tools | 5 ルール適用の billing_agent（Code 7） | `show_schema.py`（Code 1 / 4）、`tool_design_rules.py`（Code 2〜6） |
| `m05_tool_context` | M5 Tool Context | 認可と artifact を入れた billing_agent（Code 5） | `tool_context_examples.py`（Code 1〜3）、`run_with_session.py` |
| `m06_session_state` | M6 Session State | state・callback 入り billing_agent ＋ Plugin 付き `app` | `state_keys.py` / `callbacks.py` / `plugins.py` / `run_with_plugin.py` |
| `m07_multi_agent` | M7 Multi-Agent Orchestration | Parallel ＋ Sequential の support_pipeline | `specialists.py`（Code 1）、`tools.py`、`workflow_equivalents.py`（M8 への橋渡し） |
| `m08_graph_workflow` | M8 ADK 2.0 Graph Workflow | support_workflow（Code 6） | `examples.py`（Code 1〜5）、`specialists.py`、`tools.py` |
| `m09_task_collaboration` | M9 Task-Based Collaboration | support_coordinator（Code 6） | `agent_tool_example.py`（Code 5）、`tools.py` |
| `m10_grounding` | M10 Grounding | grounded_support_agent（Code 6、要 Cloud） | `.env.example`（Code 1）、`research_agents.py`（Code 2）、`structured_data.py`（Code 3）、`routing.py`（Code 4）、`mcp_examples.py`（Code 5） |
| `m11_platform` | M11 Agent Platform | load_memory 付き support_coordinator | `runners.py`（Code 3）、`run_commands.sh` |
| `m12_deploy` | M12 Deploying | デプロイ対象の support_coordinator | `.agent_engine_config.json`、`requirements.txt`、`deploy_adk_cli.sh`（Code 2 / 3）、`deploy_agents_cli.sh`（Code 4）、`deploy_sdk.py`（Code 5）、`deploy_developer_connect.py`（Code 6） |
| `m13_gemini_enterprise` | M13 Gemini Enterprise App | 公開用 description 付き support_coordinator | `check_prerequisites.sh`（素材 1）、`register_agent.sh`（素材 3）、`create_authorization.sh`（素材 5）、`publish_end_to_end.sh`（素材 7） |

各モジュールは単独で読めるよう、tool（`tools.py`）はフォルダごとに複製しています。

### 実行方法の補足

- `python -m …` 形式のスクリプトは **`agents/` フォルダで**実行します（例：`uv run python -m m05_tool_context.run_with_session`）。
- `.sh` のうち `run_commands.sh` と `deploy_agents_cli.sh` はコピーして使うコマンド集なので、丸ごと実行しても先頭で終了します。
- M10〜M13 は Google Cloud のプロジェクトが必要です。M10 だけ Cloud に切り替えるときは `m10_grounding/.env` を置きます（adk web は agent フォルダに近い `.env` を優先します）。
- `.agent_engine_config.json` は JSON なのでコメントを書けません。中身の意味は `m12_deploy/deploy_adk_cli.sh` のコメントを参照してください。

### コンソールからの登録（M13 素材 2）

Gemini Enterprise → アプリを選択 → Agents → Add agent → Custom agent via Agent Runtime。
入力するのは (1) 任意の OAuth 認可設定、(2) Agent name、(3) **Description**、(4) Agent Runtime のリソースパス（`projects/PROJECT_ID/locations/LOCATION/reasoningEngines/RESOURCE_ID`）の 4 項目です。

## 講師ガイドから変えた点（google-adk 2.9.2 で確認）

| 場所 | ガイドの記載 | このサンプル | 理由 |
| --- | --- | --- | --- |
| M8 Code 6 | router が `Event(route=[...])` で該当 specialist だけ発火し、`JoinNode` で合流 | 3 つの gate ノードに常に fan-out し、担当外の gate は LLM を呼ばず `"N/A"` を返す | `JoinNode` は前段が**すべて**完了するまで待つため、3 カテゴリ全部に該当したときしか synthesizer が動かない（ダミー LLM で再現を確認済み） |
| M8 Code 5 | instruction に `{Ticket.order_id}` | 「受け取った Ticket の order_id」と文章で指示 | `{Ticket.order_id}` は state 名として無効なので置換されず、文字のままモデルに渡る |
| M10 Code 6 | `VertexAiSearchTool` ＋ `google_search` ＋ `McpToolset` を 1 つの agent に並べる | 検索 tool 2 つに `bypass_multi_tools_limit=True` を付与 | Gemini API は組み込み検索 tool と function calling を同じリクエストに同居させられないため |
| M7 / M8 の `@node` | ― | `rerun_on_resume=True` を指定 | `ctx.run_node()` を使うノードはこれが無いと実行時に ValueError になる |
| M5 `list_invoices` | `account_id` を引数で受け取る | 認可済みの `verified_account_id` を state から読む | モデルが別の ID を渡して回り込む余地をなくすため（M5 の「認可は tool に置く」を徹底） |
| M12 Code 6 | `client.runtimes.create()` | `runtimes` が無ければ `agent_engines.create()` を使う | インストールされた SDK（1.165.1）には `agent_engines` しか無い（ガイドの「移行中」の注記どおり） |

adk web でデモしやすくするため、M5・M6 ではログイン済みユーザー（`session_user_id = "A-1001"`）を callback で補っています（本来はアプリが入れる値。コメントに明記）。
