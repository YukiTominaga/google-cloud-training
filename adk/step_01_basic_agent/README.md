# step_01_basic_agent — 最小構成の Agent

## 学べる概念

- ADK の最小単位である `Agent` の作り方（`name` / `model` / `description` / `instruction` / `generate_content_config`）
- `root_agent` という変数名の規約（CLI がこの名前を探します）
- `description`（役割の説明・転送判断に効く）と `instruction`（振る舞いの指示）の違い
- `generate_content_config` による生成パラメータ（`temperature` など）の指定
- モデル名をハードコードせず `.env` の `GEMINI_MODEL` で差し替える方法

## 対応する講義モジュール

- **M2「ADK でエージェントを開発する」**

## セットアップ

リポジトリ直下（`adk/`）で一度だけ実施します。

```bash
uv sync                 # 依存をインストール（.venv を自動作成）
cp .env.example .env    # リポジトリ直下に .env を作成し、API キー等を記入
```

`.env` は ADK が親方向にたどって読むため、リポジトリ直下に 1 つ置けば全サンプルで共有されます。

## 実行コマンド

いずれもリポジトリ直下（`adk/`）から実行します。

```bash
# 1) ブラウザの開発 UI（http://localhost:8000）。ドロップダウンで step_01_basic_agent を選択
uv run adk web

# 2) ターミナルで対話
uv run adk run step_01_basic_agent
```

構造だけを確認したい場合（API キー不要）:

```bash
uv run python verify_agents.py
```

## サンプルクエリ（試してみる）

`adk web` または `adk run step_01_basic_agent` で入力してみてください。

1. **「AI エージェントとは何か、初心者にもわかるように説明してください」** — ツールなしで一般知識から回答します。
2. **「LLM の temperature とは何ですか？」** — `generate_content_config` で設定した生成パラメータの概念を説明します。

## 期待される挙動

- 質問に対して、やさしい日本語で簡潔に回答します。
- ツールを持たないため、天気や検索など「外部情報が必要な質問」には一般知識の範囲でしか答えません
  （ツールの追加は `step_02_agent_with_tools` で学びます）。
- `instruction` を書き換えて `adk web` を再読み込みすると、応答の口調や方針が変わることを確認できます。
