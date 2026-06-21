# Learnings — ADK 教材リポジトリ

ADK 2.3.0 の実体（インストール済みパッケージ / ソース）で検証した、再利用価値のある知見。

## 2026-06-21: adk web のチャット入力はクリップボード画像の貼り付け非対応

バンドルされた adk web フロントエンド（`cli/browser/main-*.js`）の paste/onPaste 処理はテキスト/JSON
エディタ用のみで、チャット入力欄への画像ペースト（Cmd+V）には非対応。バンドル JS の改変は再インストールで
消えるため非保守的。**解決策はブラウザ内スニペット**で、adk web 自身のファイル添付フローへ流し込む。
（参考: 結果画像の取り出しは `InMemoryArtifactService.load_artifact(*, app_name, user_id, filename,
session_id=None)`。async, keyword 専用。macOS のクリップボード画像は `osascript` の
`the clipboard as «class PNGf»` でファイル化できる＝追加依存なし。）
ブラウザ内で Cmd+V を後付けするには、チャットの隠しファイル入力（`<input type=file>` で
`(change)="fileSelect.emit($event)"` と判明）に、paste 画像を `DataTransfer` 経由で
`input.files` にセットし `change` を dispatch して adk web 既存の添付フローへ流し込む
（`image_edit_studio/paste_in_adk_web.user.js`）。Tampermonkey にユーザースクリプトとして入れると
adk web を開くたび自動で有効化（毎回のコンソール貼り付けが不要）。コンソール貼り付けでも動くが、
Chrome/Edge は自衛のため初回に `allow pasting` の入力を要求する点に注意。
**拡張機能なしで恒久化する最善策**: 配信元 `index.html`（`google/adk/cli/browser/index.html`。adk web は
`/` → `/dev-ui/` リダイレクトで配信）の `</body>` 直前に同じ paste 処理の `<script>` を注入する
（`image_edit_studio/enable_paste.py`、冪等、`--disable` で除去）。`/dev-ui/` を curl して注入確認済み。
site-packages を書き換えるため `uv sync --reinstall` 等で消える→再実行が必要。

## 2026-06-21: 画像編集（Nano Banana 2）/ artifact / マルチモーダル入力（image_edit_studio）

- **Nano Banana 2 = `gemini-3-pro-image`**（通称 Nano Banana Pro）。Vertex `utaha-io`/global で利用可能なのは
  `gemini-3.1-flash-image`（高速・低コスト）, `gemini-3.1-flash-image-preview`, `gemini-3-pro-image`（高品質）。
  Imagen 系（`edit_image` の `EditMode`/マスク）は一覧に出ず未確認。Nano Banana は「画像＋プロンプト」で in/out-painting する。
- **画像編集の呼び出し**（`google-genai 2.9.0`）: `client.aio.models.generate_content(model, contents=[image_part, prompt],
config=types.GenerateContentConfig(response_modalities=["IMAGE"]))`。出力画像は
  `resp.candidates[0].content.parts[].inline_data.data`（バイト）/`.mime_type`。`.aio` で非同期呼び出し可。
- **アップロード画像の取得**: `adk web` の添付画像はユーザーメッセージの `inline_data` Part として届き、ツールは
  `tool_context.user_content.parts` から取得できる（実機相当のプログラム模擬で確認済み）。
- **artifact**: `tool_context.save_artifact(filename, types.Part.from_bytes(data=, mime_type=))` は **async**（`await` 必須）。
  `load_artifact` も async。保存した画像は `adk web` の画面に表示される。
- **レート制限**: 画像モデルはクォータが小さく、連続実行で `429 RESOURCE_EXHAUSTED` になりやすい。検証では元画像を
  `/tmp` にキャッシュして再生成を避け、バックオフ再試行した。
- **テスト用画像の注意**: 1x1 PNG は API に "Failed to decode image data" で弾かれる。zlib で 64x64 以上の有効な PNG を作る。

## 2026-06-21: エージェントのディレクトリ名は英字始まりにする（数字始まりは実行時に落ちる）

**重要な落とし穴。** `01_basic_agent` のような数字始まりディレクトリは `AgentLoader`（`verify_agents.py`
や `adk api_server` の `/list-apps`）では**ロードできてしまう**が、`adk run` / `adk web` で実際に
**ターンを実行する瞬間に落ちる**。`adk` CLI は素の `root_agent` をディレクトリ名で
`App(name=<dir>)` にラップする（`cli/cli.py:_to_app`）。`App` の name バリデーションは
「先頭は英字、以降は英数字 / `_` / `-`」を要求するため、`01_...` は
`Invalid app name '01_basic_agent'` で `ValidationError`。
ロード検証だけでは捕捉できず、実 CLI を回して初めて判明した。対策としてディレクトリを
`step_01_basic_agent` … と**英字始まりにリネーム**して解消（`adk run` 実応答まで確認済み）。
※ 既に `app = App(name=...)` を公開しているサンプルは、`_to_app` がそのまま返すので
有効な name さえ付けていれば数字始まりでも一応動くが、素の `root_agent` 公開サンプルは不可。

## 2026-06-21: .env はリポジトリ直下に 1 つでよい（親方向に探索される）

`cli/utils/envs.py` の `load_dotenv_for_agent` はエージェントの dir から**親方向にルートまで**
`.env` を探す（`_walk_to_root_until_found`）。各エージェント dir にコピーする必要はなく、
リポジトリ直下に 1 つ置けば全サンプルが共有する。最も近い `.env` が優先される。

## 2026-06-21: ADK 2.3.0 の DEFAULT_MODEL は gemini-3.5-flash

`LlmAgent.DEFAULT_MODEL = "gemini-3.5-flash"`（`agents/llm_agent.py`）。`model` 未指定時の既定。
教材では env `GEMINI_MODEL`（既定 `gemini-3.5-flash`）で一元管理し、ハードコードしない。

## 2026-06-21: google_search は他ツールと同一エージェントで併用不可（回避策あり）

`google_search`（`GoogleSearchTool`）はモデル内部実行の組み込みツール。共有シングルトンを
カスタム FunctionTool と同じ `tools=[...]` に並べると実行時にエラー。回避策は 2 つ:
(1) google_search だけを持つ専用エージェントを作り `AgentTool(agent=...)` で親に載せる（明示・推奨）。
(2) `GoogleSearchTool(bypass_multi_tools_limit=True)` を使うと ADK が `_convert_tool_union_to_tools`
（`agents/llm_agent.py`）で内部的に AgentTool ラップする。組み込みツールは before_tool_callback が
発火しない（モデル側で実行されるため）点にも注意。

## 2026-06-21: コールバックのシグネチャと短絡（2.3.0）

ctx 型は `google.adk.agents.context.Context`（`.state .actions .agent_name .invocation_id` 等）。

- `before_agent_callback(ctx) -> Optional[types.Content]`（Content 返却でエージェント短絡）
- `before_model_callback(ctx, llm_request) -> Optional[LlmResponse]`（LlmResponse 返却でモデル skip）
- `after_model_callback(ctx, llm_response) -> Optional[LlmResponse]`（partial チャンクに注意）
- `before_tool_callback(tool, args, ctx) -> Optional[dict]`（dict 返却でツール skip）
- `after_tool_callback(tool, args, ctx, tool_response) -> Optional[dict]`
- 2.x 新規: `on_model_error_callback` / `on_tool_error_callback`（第3/4引数に Exception）。
  ツール/コールバックで広い `except Exception:` を書くと `retry_config` の自動リトライや HITL の
  中断（`NodeInterruptedError`、`workflow/_errors`）を握りつぶすため禁止。具体例外のみ捕捉する。

## 2026-06-21: App / Plugin パターン

`from google.adk.apps import App` → `App(name, root_agent, plugins=[...], events_compaction_config, ...)`。
`agent.py` で `root_agent` の代わりに `app` を公開すると loader が App を優先ロードする。
Plugin は `from google.adk.plugins import BasePlugin` を継承（**`ContextFilterPlugin` は実体に存在しない**）。
BasePlugin のフックは全てキーワード専用: `on_user_message_callback(*, invocation_context, user_message)`,
`before_agent_callback(*, agent, callback_context)`, `before_tool_callback(*, tool, tool_args, tool_context)`,
`after_run_callback(*, invocation_context)` 等。App 全体に横断適用される。

## 2026-06-21: Cloud Trace の有効化は CLI フラグ（旧 env 変数は廃止）

旧資料の `AF_TRACE_TO_CLOUD` 環境変数は現行に無い。`adk web` / `adk api_server` の
`--trace_to_cloud`（Cloud Trace）または `--otel_to_cloud`（OTel → Cloud Trace + Logging）を使う。

## 2026-06-21: gemini-3.5-flash は Vertex AI の global エンドポイントで動く

ADC + Vertex（`GOOGLE_GENAI_USE_VERTEXAI=TRUE`）で `gemini-3.5-flash` を呼ぶには
`GOOGLE_CLOUD_LOCATION=global` を使う（`us-central1` ではない）。新しめの Gemini モデルは
global エンドポイント提供。01〜app まで全サンプルがこの構成（project=utaha-io）でライブ動作確認済み。

## 2026-06-21: App の name はディレクトリ名に合わせる

`App(name=...)` がディレクトリ名と異なると、Runner 実行時に "App name mismatch" 警告が出る
（loader が origin app name にディレクトリ名を記録するため）。`app_research_assistant/agent.py`
では `App(name="app_research_assistant")` とディレクトリ名に揃えて回避。

## 2026-06-21: load_dotenv() は heredoc 実行だと失敗する

`python - <<'PY'`（stdin）経由で `load_dotenv()`（引数なし）を呼ぶと、`find_dotenv()` が
呼び出し元フレームを辿れず `AssertionError`。実ファイル実行（`uv run python foo.py`）では問題ない。
テストハーネスでは `os.environ` を直接設定するか `load_dotenv(dotenv_path=...)` を使う。

## 2026-06-21: adk CLI は venv 内。常に `uv run adk ...`

`adk` は PATH に無く `.venv` 内にある。`uv run adk web` / `uv run adk run <dir>` で実行する。
Custom 分岐は `BaseAgent` を継承し `async def _run_async_impl(self, ctx)` をオーバーライド、
子フィールドを型付きで宣言し `super().__init__(..., sub_agents=[...])` に渡す（`model_config =
{"arbitrary_types_allowed": True}`）。
