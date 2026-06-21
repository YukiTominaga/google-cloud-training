"""app_research_assistant — 統合ミニアプリ（リサーチアシスタント）。

基礎で学んだ要素を 1 つに統合した実用例です。

  - ワークフローエージェント: SequentialAgent（全体）/ ParallelAgent（並列調査）
    / LoopAgent（批評と改善の反復）
  - State: 各段の output_key と instruction 内の {key} で結果を受け渡し
  - Callback: 入力ガードレール（planner の before_model_callback）
  - Plugin: App 全体に横断適用するロギング（UsageLoggerPlugin）
  - App パターン: root_agent の代わりに `app = App(...)` を公開（ADK の loader は
    `app` を優先して読み込みます）

実行:
    uv run adk web   # ドロップダウンで app_research_assistant を選び対話
"""

from __future__ import annotations

from google.adk.agents import SequentialAgent
from google.adk.apps import App

from .plugins import UsageLoggerPlugin
from .sub_agents import critic_loop, parallel_search, planner, writer

# 全体は「計画 → 並列調査 → 執筆 → 批評ループ」の決定的なパイプラインです。
research_pipeline = SequentialAgent(
    name="research_pipeline",
    sub_agents=[planner, parallel_search, writer, critic_loop],
)

# App パターン: plugins / state / 各種設定をまとめて宣言します。
# `root_agent` ではなく `app` を公開すると、ADK はこの App を読み込みます。
# App の name はディレクトリ名（= adk web 上のアプリ名）に合わせます。
app = App(
    name="app_research_assistant",
    root_agent=research_pipeline,
    plugins=[UsageLoggerPlugin()],
)
