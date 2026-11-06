# GCP Assistant (ADK 研修用プロジェクト)

Google ADK (Agent Development Kit) と Python を用いたカスタムエージェント開発研修用プロジェクトです。仕様駆動開発（Gherkin / pytest-bdd）を採用しています。

## 仕様の場所

| 機能 | 仕様書 | フィーチャー定義 | ステップ定義 |
| :--- | :--- | :--- | :--- |
| **GCP Assistant エージェント本体** | [`specs/gcp-assistant-agent.md`](specs/gcp-assistant-agent.md) | [`tests/features/gcp_assistant_agent.feature`](tests/features/gcp_assistant_agent.feature) | [`tests/step_defs/test_gcp_assistant_agent.py`](tests/step_defs/test_gcp_assistant_agent.py) |
| **GCP プロジェクト取得ツール** | [`specs/get-current-gcp-project.md`](specs/get-current-gcp-project.md) | [`tests/features/get_current_gcp_project.feature`](tests/features/get_current_gcp_project.feature) | [`tests/step_defs/test_get_current_gcp_project.py`](tests/step_defs/test_get_current_gcp_project.py) |

## ツール一覧

- `get_current_gcp_project`: 現在の gcloud アクティブプロジェクト ID を安全に取得（実装済み）

## エージェント構成 (`gcp_assistant`)

Google ADK 2.0 の Graph API（`Workflow` + `LlmAgent`）を採用し、モデルには `"gemini-4-argon"` を使用しています。

- **ワークフロー (`root_agent`)**: `Workflow(name="gcp_assistant", edges=[("START", gcp_assistant_node)])`
- **内包ノード (`gcp_assistant_node`)**: `LlmAgent(name="gcp_assistant_node", model="gemini-4-argon", tools=[get_current_gcp_project])`
- **システム指示 (instruction)**:
  1. GCP プロジェクト特定時は推測を行わず `get_current_gcp_project` ツールを使用する。
  2. 読み取り専用（read-only）操作を徹底し、リソースの変更・削除・作成は一切行わない。
  3. アクセストークンや秘密鍵などの機密情報を会話ログや出力に含めない。


## セットアップ

依存パッケージのインストールと環境構築を行います。

```bash
uv sync
```

### テスト

BDD シナリオテストを実行します。

```bash
uv run pytest
```

### Lint・フォーマットチェック

Ruff による静的解析とフォーマット確認を実行します。

```bash
uv run ruff check . && uv run ruff format --check .
```

## agy の telemetry を Google Cloud へ送信する(任意)

`agy` の `Stop` hook([`.agents/hooks.json`](.agents/hooks.json))が、ターンごとの実行内容を
親子関係付きの trace として Cloud Trace へ送信します。スクリプトは
[`.agents/hooks/otel_gcp.py`](.agents/hooks/otel_gcp.py) です。依存パッケージは `hooks` 依存グループにあり、
`uv sync` で `.venv` に入ります(hook もこの `.venv` を使います)。

```
agy.turn (ユーザー入力から応答完了まで)
 └ agy.model_call (トークン数・キャッシュ率・モデル名・応答/思考の本文)
    └ agy.tool.<名前> (コマンド・ファイルパスなどの引数)
```

### 事前準備

```bash
gcloud auth application-default login                       # ADC で認証
gcloud services enable telemetry.googleapis.com --project <プロジェクトID>
export GOOGLE_CLOUD_PROJECT=<プロジェクトID>                  # agy を起動するシェルで設定
```

- ADC のアカウントに `roles/telemetry.tracesWriter` が必要です。
- `GOOGLE_CLOUD_PROJECT` が未設定の場合は、ADC のプロジェクトを使います。
- 送信に失敗しても hook は成功扱いで終了し、エージェントは止まりません。

### 送信される内容と注意

- ユーザー入力、応答本文、思考の本文、実行したコマンド、サブエージェントへのプロンプトを**切り詰めずに**送信します。
  `--token` や `API_KEY=` などの機密値らしきものは `***` に置換しますが、完全ではありません。
- 送信したくない場合は、`.agents/hooks.json` の `enabled` を `false` にしてください。

### 動作確認(送信なし)

```bash
echo '{"conversationId":"t","modelName":"x","transcriptPath":"<transcript.jsonl のパス>"}' \
  | AGY_OTEL_DRY_RUN=1 .venv/bin/python .agents/hooks/otel_gcp.py Stop
```

## 起動

ADK Web UI を起動してエージェントを実行・検証します。

```bash
uv run adk web
```

## 評価 (Evaluation)

`agents-cli eval` およびローカル評価ランナーによる品質評価（シナリオ適合性、セキュリティ準拠）を実行します。

```bash
# スタンドアロン評価ランナーの実行（全9シナリオのスコア算出）
python3 tests/eval/run_eval.py

# agents-cli eval コマンド群のヘルプ確認
agents-cli eval --help

# pytest 経由での評価テスト実行
uv run pytest tests/eval/test_eval.py
```

