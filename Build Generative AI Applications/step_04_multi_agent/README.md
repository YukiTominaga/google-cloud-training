# step_04_multi_agent — マルチエージェント（転送 / ワークフロー / Custom）

## 学べる概念

- **階層型マルチエージェント（転送 / transfer）**: 親（coordinator）が `sub_agents` の
  `description` を見て、適切な子へ制御を渡す（`agent.py`）
- **LLM ベースエージェント vs ワークフローエージェント**の違い:
  - LLM ベース（転送）… 次に何をするかを **LLM が自律的に判断**（柔軟だが非決定的）
  - ワークフロー … 制御フローが **決定的**（`SequentialAgent` / `ParallelAgent` / `LoopAgent`）
- **`output_key` と `{key}` テンプレート**で state を介してデータを受け渡す
- `LoopAgent` の `max_iterations` と、ループ脱出ツール `exit_loop`
- **Custom Agent**: `BaseAgent` を継承し `_run_async_impl` で条件分岐・動的選択を自作（`workflows.py`）
- **転送（transfer）と `AgentTool`（02 で学習）の違い**: 転送は制御を渡し戻らない／
  AgentTool は呼び出して結果を受け取り制御は親に戻る

## 対応する講義モジュール

- **M3「ADK でマルチエージェントシステムを構築する」**

## セットアップ

リポジトリ直下で `uv sync` と `cp .env.example .env`（API キー記入）を済ませてください。

## 実行コマンド

```bash
# A) 階層型転送（受付 → 担当へ転送）を対話で試す
uv run adk web                       # ドロップダウンで step_04_multi_agent を選択
uv run adk run step_04_multi_agent

# B) ワークフロー（Sequential/Parallel/Loop）と Custom 分岐をまとめて実行
uv run python step_04_multi_agent/workflows.py
```

## サンプルクエリ（試してみる）

転送デモ（`adk web` / `adk run step_04_multi_agent`）で入力してみてください。

1. **「請求書の支払い方法を教えてください」** — 受付から `billing_agent` へ転送されます。
2. **「アプリが起動しません。どうすればいいですか？」** — 受付から `tech_agent` へ転送されます。

## 期待される挙動

- **A) 転送**: 「請求書について」→ `billing_agent` へ、「エラーが出る」→ `tech_agent` へ転送されます。
  `adk web` の画面では、どの担当が応答したか（author）が確認できます。
- **B) workflows.py**:
  1. Sequential: アウトライン作成 → それを文章へ展開（前段の結果を後段が参照）
  2. Parallel: 利点と欠点を同時に生成
  3. Loop: スローガンを最大 3 回まで改善（`exit_loop` か `max_iterations` で停止）
  4. Custom: `state["topic"]="tech"` に応じて技術担当へ動的に分岐

## メモ: 使い分け

「次の一手を AI に任せたい」なら LLM ベース（転送 / AgentTool）、「手順を固定したい」なら
ワークフローエージェント、「独自の条件分岐を書きたい」なら Custom（BaseAgent）を選びます。
