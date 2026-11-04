# GCP Assistant (ADK 研修用プロジェクト)

Google ADK (Agent Development Kit) と Python を用いたカスタムエージェント開発研修用プロジェクトです。仕様駆動開発（Gherkin / pytest-bdd）を採用しています。

## 仕様の場所

- 仕様書: [`specs/get-current-gcp-project.md`](specs/get-current-gcp-project.md)
- フィーチャー定義: [`tests/features/get_current_gcp_project.feature`](tests/features/get_current_gcp_project.feature)
- ステップ定義: [`tests/step_defs/test_get_current_gcp_project.py`](tests/step_defs/test_get_current_gcp_project.py)

## ツール一覧

- `get_current_gcp_project`: 現在の gcloud アクティブプロジェクト ID を取得（仕様のみ・未実装）

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

## 起動

ADK Web UI を起動してエージェントを実行・検証します。

```bash
uv run adk web
```
