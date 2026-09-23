# step_02_agent_with_tools — ツールを使う Agent

## 学べる概念

- **カスタム Function Tool**: 素の Python 関数を `tools=[...]` に渡すだけでツールになること
- **docstring と型ヒントが LLM のツール選択に直結する**こと（docstring は LLM 向けの仕様書）
- ツール戻り値の設計（`status` を含む dict、引数を変更しないイミュータブルな実装）
- **組み込みツール `google_search`** の使い方と制約
- **組み込みツールは他ツールと同一エージェントで併用できない**ため、専用エージェントに隔離し
  `AgentTool` で包んで親に渡す定石パターン
- `AgentTool`（呼び出して結果を受け取る）と、後の `step_04_multi_agent` で学ぶ転送（transfer）の違い

## 対応する講義モジュール

- **M2「ADK でエージェントを開発する」**

## セットアップ

リポジトリ直下（`adk/`）で `uv sync` と `cp .env.example .env`（API キー記入）を済ませてください
（詳細は親ディレクトリの README を参照）。`google_search` を実際に動かすにはモデルへのアクセスが必要です。

## 実行コマンド

```bash
# ブラウザ UI（ドロップダウンで step_02_agent_with_tools を選択）
uv run adk web

# ターミナルで対話
uv run adk run step_02_agent_with_tools

# REST API サーバとして起動（http://localhost:8000）
uv run adk api_server
```

`api_server` 起動後の呼び出し例（セッション作成 → メッセージ送信）:

```bash
# セッションを作成
curl -X POST http://localhost:8000/apps/step_02_agent_with_tools/users/u1/sessions/s1

# メッセージを送信
curl -X POST http://localhost:8000/run \
  -H "Content-Type: application/json" \
  -d '{
    "app_name": "step_02_agent_with_tools",
    "user_id": "u1",
    "session_id": "s1",
    "new_message": {"role": "user", "parts": [{"text": "100 USD は何円ですか？"}]}
  }'
```

## サンプルクエリ（試してみる）

`adk web` または `adk run step_02_agent_with_tools` で入力してみてください。

1. **「100 USD は日本円でいくらですか？」** — カスタムツール `convert_currency` が呼ばれます。
2. **「最近の生成 AI に関する話題を 1 つ教えてください」** — `web_search_assistant`（`google_search`）経由で検索して答えます。

## 期待される挙動

- 「100 USD は何円？」→ `convert_currency` が呼ばれ、固定レートで換算した金額を答えます。
- 「対応している通貨は？」→ `list_supported_currencies` が呼ばれ、コード一覧を答えます。
- 「今日のニュースを教えて」など最新情報 → `web_search_assistant`（google_search）経由で検索して答えます。
- 未対応通貨（例: "BTC"）を指定 → ツールが `status=error` を返し、エージェントがその旨を説明します。

## 補足: 組み込みツールの併用制約

`google_search` を `convert_currency` などと**同じ** `tools=[...]` に直接並べると、実行時に
「組み込みツールは他ツールと併用不可」というエラーになります。本サンプルのように専用エージェント＋
`AgentTool` で隔離するのが定石です。なお `GoogleSearchTool(bypass_multi_tools_limit=True)` を使うと
ADK が内部で自動的に AgentTool ラップを行うため、同一 `tools` に並べても動作します（仕組みを隠す近道）。
