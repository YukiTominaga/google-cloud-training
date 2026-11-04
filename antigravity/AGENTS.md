# AGENTS.md

## 目的
Google Cloud 研修受講者を対象とした、Google ADK（`google-adk`, Python）によるカスタムエージェント開発研修用プロジェクト。

## リポジトリ地図
- `specs/`: 機能ごとの仕様（唯一の正・北極星。コードは仕様から再生成可能な使い捨てとして扱う）
- `tests/features/`: 仕様と同一文言の Gherkin シナリオ（実行可能テストファイル）
- `tests/step_defs/`: pytest-bdd のステップ定義
- `tests/eval/`: agents-cli の評価データセットとメトリクス
- `gcp_assistant/`: ADK エージェント本体
- `.agents/`: エージェント用ハーネス（rules, agents, skills）

## コマンド（すべて uv 経由、Makefile は使用禁止）
- セットアップ: `uv sync`
- テスト: `uv run pytest`
- lint: `uv run ruff check . && uv run ruff format --check .`
- 起動: `uv run adk web`
- 評価: `agents-cli eval`（利用可能なサブコマンド: `run`, `generate`, `grade`, `compare`, `metric`）

## 規約
- Python 3.11+、型ヒント必須、ruff 準拠
- ADK ツール関数: 必ず dict を返し `"status"` キーを持つ（成功: `"success"`、失敗: `"error"`）
- docstring とコメントは日本語、会話応答も日本語

## 仕様駆動の原則
1. 仕様がない機能は実装しない。まず spec-writer が `specs/<機能名>.md` を書き、ユーザーが承認する
2. 実装指示は必ず「`specs/<機能名>.md` の Scenario N」の形式で出す（自然言語の説明のみで implementer を起動しない）
3. `specs/` の Gherkin と `tests/features/` の `.feature` は同一文言を保つ（片方のみの変更は禁止）
4. 実装中に仕様と異なる判断が必要になったら、コードより先に仕様を更新し、ユーザーに差分を提示する
5. 検証は「Scenario ごとに Given / When / Then が満たされたか」を spec-verifier が実出力で示す（pytest 合格のみでは完了としない）

## 作業の進め方（必須フロー）
`explorer` / `gcp-inspector`（調査）
  → `spec-writer`（仕様策定）
  → **ユーザー承認**
  → `implementer`（Scenario 単位で実装）
  → `spec-verifier`
  → `reviewer`
  → `evaluator`
  → `doc-writer`

## 完了の定義
- 全 Scenario が spec-verifier で PASS
- reviewer に High の指摘なし
- evaluator の全メトリクスが目標スコアに到達
- README と仕様（バージョン固定等含む）が最新

## GCP 操作
- `gcloud` は読み取り系のみ自動実行可、変更系は必ず事前確認。詳細は `.agents/rules/gcp-commands.md`

## 触らないもの
- `.env`、認証情報ファイル、`~/.config/gcloud`、Git 履歴

## 参照先
- `.agents/rules/`
- `.agents/agents/`
- `.agents/skills/`
