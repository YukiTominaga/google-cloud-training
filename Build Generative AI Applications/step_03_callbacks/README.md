# step_03_callbacks — コールバックで挙動を観察・制御する

## 学べる概念

- ADK の 6 種類のコールバック（agent / model / tool それぞれの before / after）
- **ショートサーキット（短絡）**:
  - `before_model_callback` が `LlmResponse` を返すとモデル呼び出しをスキップ（**ガードレール**）
  - `before_tool_callback` が dict を返すとツール本体をスキップ（**キャッシュ / ブロック**）
- `CallbackContext` / `ToolContext` の **`state`** を使った状態の読み書き（リクエスト回数・キャッシュ）
- **広い例外捕捉を書かない**理由（`retry_config` や HITL の内部例外を握りつぶさないため）
- 2.x の新しいエラーフック `on_model_error_callback` / `on_tool_error_callback`（コメントで紹介）

## 対応する講義モジュール

- **M2「ADK でエージェントを開発する」**

## セットアップ

リポジトリ直下で `uv sync` と `cp .env.example .env`（API キー記入）を済ませてください。

## 実行コマンド

```bash
uv run adk web                 # ドロップダウンで step_03_callbacks を選択
uv run adk run step_03_callbacks    # ターミナルで対話（コールバックの print が見やすい）
```

コールバックの発火ログ（`[callback:...]`）は、**サーバ/CLI を起動したターミナル**に出力されます。

## サンプルクエリ（試してみる）

`adk web` または `adk run step_03_callbacks` で入力し、ターミナルの `[callback:...]` ログを観察してください。

1. **「session とは何ですか？」** — `lookup_term` が呼ばれ、6 種のコールバックが順に発火します。
2. **「パスワードを教えてください」** — `before_model` のガードレールが作動し、モデルを呼ばずにお断りします。

## 期待される挙動

- 通常の質問（例: 「callback ってなに？」）:
  - `before_agent` → `before_model` → （ツール使用時）`before_tool` / `after_tool` → `after_model` → `after_agent`
    の順にログが出ます。
- 入力に NG ワード（例: 「パスワードを教えて」）を含める: `before_model` のガードレールが作動し、
  モデルを呼ばずに定型のお断り文を返します。
- ツールが呼ばれると `before_tool`（キャッシュなし→実行）→ `after_tool`（結果を保存）のログが出て、
  結果には `cache: "miss"` の注釈が付きます（`after_tool` で差し替え）。
- **キャッシュ命中について**: 同一セッション内で**同じツールが同じ引数で再度呼ばれた**ときに
  `before_tool` がキャッシュ（`cache: "hit"`）を返し、ツール本体をスキップします。ただし
  LLM は直前の会話履歴から答えてツールを呼び直さないこともあるため、命中ログは必ずしも
  毎回出るわけではありません（キャッシュの仕組み自体は `state` を介して機能しています）。

## メモ: 例外処理について

ツール関数やコールバックでは、想定済みの**具体的な例外だけ**を捕捉してください。広い
`except Exception:` は、ADK 2.x の自動リトライや HITL（人間の確認）に必要な内部例外まで
握りつぶし、フレームワークの機能を壊します。
