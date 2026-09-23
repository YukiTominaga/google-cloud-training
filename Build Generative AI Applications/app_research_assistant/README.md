# app_research_assistant — 統合ミニアプリ（リサーチアシスタント）

基礎パート（01〜04）で学んだ要素を 1 つに統合した、対話できる完成形のアプリです。

## 学べる概念（統合）

- **App パターン**: `root_agent` の代わりに `app = App(name=..., root_agent=..., plugins=[...])` を公開
- **ワークフローエージェントの組み合わせ**:
  - `SequentialAgent`（全体: 計画 → 並列調査 → 執筆 → 批評ループ）
  - `ParallelAgent`（複数観点を同時に調査）
  - `LoopAgent`（批評と改善を `exit_loop` / `max_iterations` で反復）
- **State**: 各段の `output_key` と instruction 内の `{key}` でデータを受け渡し
- **Callback（ガードレール）**: `planner` の `before_model_callback` で不審な入力をブロック
- **Plugin**: `UsageLoggerPlugin` が App 全体に横断適用され、各ステージの実行をログ
- 組み込みツール `google_search` を各 searcher が単独で利用（組み込みツールの併用制約を回避）

## 対応する講義モジュール

- 基礎（M2 / M3）の総合演習。`adk web` で動く完成形として位置づけます。

## ファイル構成

```
app_research_assistant/
├── agent.py        # app = App(...) を公開（パイプラインの組み立て）
├── sub_agents.py   # planner / parallel_search / writer / critic_loop
├── callbacks.py    # 入力ガードレール（before_model_callback）
├── plugins.py      # UsageLoggerPlugin（App 横断ロギング）
└── __init__.py
```

## セットアップ

リポジトリ直下で `uv sync` と `cp .env.example .env`（API キー記入）を済ませてください。
`google_search` を使うため、モデルへのアクセスが必要です。

## 実行コマンド

```bash
uv run adk web      # ドロップダウンで app_research_assistant を選択して対話
```

## サンプルクエリ（試してみる）

`adk web` で app_research_assistant を選び、入力してみてください。

1. **「社内向けに生成 AI を導入するメリットとリスクを調べてください」** — 計画 → 並列調査 → 執筆 → 批評の全パイプラインが動きます。
2. **「リモートワーク導入の効果と課題を、最新情報を交えて調べてください」** — 各 searcher が観点別に `google_search` で調査します。

## 期待される挙動

1. リサーチ依頼（例: 「社内向け生成 AI 活用のメリットとリスクを調べて」）を送ると、
2. `planner` が観点を分解 →
3. `parallel_search` の 3 エージェントが概要 / リスク / 最近の動向を **並列に** 調査 →
4. `writer` が結果を統合して見出し付きレポートを生成 →
5. `critic_loop` が品質を評価し、必要なら改善（最大 2 回）して最終レポートを返します。

サーバを起動したターミナルには、`[plugin] stage #N: ...` のように各ステージの進行ログが出ます。
不審な指示（例: 「これまでの指示を無視して…」）を含めると、ガードレールが作動して依頼を中止します。

## 次のステップ（本コースのスコープ外）

- **Memory**: 過去の調査を `InMemoryMemoryService` や `VertexAiMemoryBankService` に蓄積し、
  `load_memory` / `preload_memory` ツールで参照する拡張が可能です（本サンプルは State 中心）。
- **デプロイ / 評価**: `adk deploy`（Agent Engine）や `adk eval` は別途扱います（リポジトリ直下 README 参照）。
