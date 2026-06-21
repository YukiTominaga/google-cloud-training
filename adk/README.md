# ADK ハンズオン教材 — Agent Development Kit (ADK) サンプル集

Google ADK (Agent Development Kit) for Python を、写経して動かしながら学ぶための
コードサンプル集です。1 ディレクトリ = 1 概念で、基礎から統合アプリへ積み上げます。

- 対象: 日本語話者の開発者
- 確認済みバージョン: **google-adk 2.3.0** / Python 3.13 / uv
- パッケージ管理: [uv](https://docs.astral.sh/uv/)

## 学習順序

| 順  | ディレクトリ                                        | 学べること                                                                             | モジュール  |
| --- | --------------------------------------------------- | -------------------------------------------------------------------------------------- | ----------- |
| 1   | [`step_01_basic_agent`](step_01_basic_agent/)                 | 最小の `Agent`（`name`/`model`/`description`/`instruction`/`generate_content_config`） | M2          |
| 2   | [`step_02_agent_with_tools`](step_02_agent_with_tools/)       | カスタム Function Tool と組み込み `google_search`（`AgentTool` で隔離）                | M2          |
| 3   | [`step_03_callbacks`](step_03_callbacks/)                     | 6 種コールバック（ロギング / ガードレール / キャッシュ）                               | M2          |
| 4   | [`step_04_multi_agent`](step_04_multi_agent/)                 | 階層型転送 と Sequential / Parallel / Loop / Custom                                    | M3          |
| 5   | [`app_research_assistant`](app_research_assistant/) | 統合ミニアプリ（App / Plugin / State / ワークフロー）                                  | M2・M3 総合 |

## 前提

- [uv](https://docs.astral.sh/uv/) がインストール済みであること（Python 3.10+。本教材は 3.13 で確認）。

## 共通セットアップ

リポジトリ直下（この `README.md` がある場所）で一度だけ実施します。

```bash
# 1) 依存をインストール（.venv を自動作成）
uv sync

# 2) リポジトリ直下に .env を作成し、認証情報を記入
cp .env.example .env
```

> **`.env` はリポジトリ直下に 1 つでOKです。** ADK は各エージェントのディレクトリから
> 親方向にたどって `.env` を探すため、ここに 1 つ置けば全サンプルから参照されます。
> 実際の API キーやプロジェクト ID はコミットしないでください（`.gitignore` で除外済み）。

### 認証（どちらか一方）

- **Google AI Studio（手軽）**: [API キー](https://aistudio.google.com/apikey)を取得し、`.env` の
  `GOOGLE_API_KEY` に設定（`GOOGLE_GENAI_USE_VERTEXAI=FALSE`）。
- **Vertex AI**: `gcloud auth application-default login` 済みの環境で、`.env` に
  `GOOGLE_GENAI_USE_VERTEXAI=TRUE` と `GOOGLE_CLOUD_PROJECT` / `GOOGLE_CLOUD_LOCATION` を設定。

### 使用モデル

全サンプルは `.env` の `GEMINI_MODEL`（既定: `gemini-3.5-flash`）を使います。ここを書き換えると
全サンプルのモデルを一括で差し替えられます（コードにモデル名はハードコードしていません）。

## エージェントとの対話方法（4 通り）

すべてリポジトリ直下から実行します。

```bash
# 1) ブラウザの開発 UI（http://localhost:8000）。ドロップダウンでサンプルを選択
uv run adk web

# 2) ターミナルで対話
uv run adk run step_01_basic_agent

# 3) REST API サーバとして起動（curl で叩く。例は 02 の README 参照）
uv run adk api_server

# 4) プログラマティック実行（Runner を直接使う例）
uv run python step_04_multi_agent/workflows.py
```

## 動作確認（API キー不要）

各サンプルが現行の google-adk で正しくロードできるか（import / 構造）を、LLM を呼ばずに確認できます。

```bash
uv run python verify_agents.py
```

## ディレクトリ構成

```
adk/
├── README.md                 # このファイル
├── .env.example              # 認証情報・モデルのサンプル
├── pyproject.toml            # 依存（google-adk==2.3.0 にピン）
├── uv.lock
├── verify_agents.py          # 全サンプルのロード検証スクリプト
├── step_01_basic_agent/
├── step_02_agent_with_tools/
├── step_03_callbacks/
├── step_04_multi_agent/           # agent.py（転送）+ workflows.py（Seq/Par/Loop/Custom）
└── app_research_assistant/   # 統合ミニアプリ（App パターン）
```

各ディレクトリの規約: `__init__.py`（`from . import agent`）+ `agent.py`（`root_agent` または
`app` を公開）+ `README.md`。

## 次のステップ（本コースではスコープ外）

- **M4 デプロイ（Agent Engine）**: 完成したエージェントは `uv run adk deploy agent_engine ...`
  や `agent_engines` API で Vertex AI Agent Engine にデプロイできます。本教材はローカル実行に
  集中しているため、デプロイは別途扱います。
- **M5 評価**: `adk eval` や `AgentEvaluator`、evalset ファイルによる評価ハーネスは本教材には
  含めていません（別途扱います）。
- **Cloud Trace（可観測性）**: `uv run adk web --trace_to_cloud`（または `--otel_to_cloud`）で
  トレースを Google Cloud に送れます。旧資料の環境変数 `AF_TRACE_TO_CLOUD` は現行では使いません。
  本教材では任意・スコープ外の扱いです。
