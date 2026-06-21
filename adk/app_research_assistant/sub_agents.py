"""リサーチアシスタントを構成するサブエージェント群。

パイプライン（agent.py で SequentialAgent に組み立て）:

    planner ──▶ parallel_search ──▶ writer ──▶ critic_loop
   (計画立案)   (並列で多角的に調査)  (統合執筆)   (批評と改善の反復)

各段は `output_key` で結果を session state に書き、後続が instruction の
`{key}` でそれを参照します（State を介したデータ受け渡し）。
"""

from __future__ import annotations

import os

from google.adk.agents import LlmAgent, LoopAgent, ParallelAgent
from google.adk.tools import exit_loop, google_search

from .callbacks import block_unsafe_input

MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")


# 1) 計画立案: 依頼を調査観点に分解する。
planner = LlmAgent(
    name="planner",
    model=MODEL,
    description="リサーチ依頼を調査すべき観点に分解する。",
    instruction=(
        "ユーザーのリサーチ依頼を読み、調べるべき観点を「概要」「論点・リスク」"
        "「最近の動向」の 3 つに整理し、それぞれ何を調べるべきか箇条書きで示してください。"
    ),
    output_key="plan",
    # 入力ガードレール（不審な指示をブロック）。
    before_model_callback=block_unsafe_input,
)


# 2) 並列調査: 同じ計画を別々の観点から google_search で調べる。
#    各 searcher は google_search だけを持つ（組み込みツールは単独で持たせる）。
def _searcher(name: str, focus: str, output_key: str) -> LlmAgent:
    return LlmAgent(
        name=name,
        model=MODEL,
        description=f"{focus}の観点で調べる。",
        instruction=(
            f"次の調査計画のうち「{focus}」に絞り、google_search で最新情報を調べ、"
            f"出典を踏まえて日本語で簡潔に要約してください:\n{{plan}}"
        ),
        tools=[google_search],
        output_key=output_key,
    )


overview_searcher = _searcher("overview_searcher", "概要・基本事実", "research_overview")
risk_searcher = _searcher("risk_searcher", "論点・リスク", "research_risks")
recent_searcher = _searcher("recent_searcher", "最近の動向", "research_recent")

parallel_search = ParallelAgent(
    name="parallel_search",
    sub_agents=[overview_searcher, risk_searcher, recent_searcher],
)


# 3) 執筆: 並列調査の結果を統合してレポートにまとめる。
writer = LlmAgent(
    name="writer",
    model=MODEL,
    description="調査結果を統合して構造化レポートを書く。",
    instruction=(
        "次の 3 つの調査結果を統合し、見出し付きの日本語レポートにまとめてください。\n\n"
        "## 概要\n{research_overview}\n\n"
        "## 論点・リスク\n{research_risks}\n\n"
        "## 最近の動向\n{research_recent}"
    ),
    output_key="report",
)


# 4) 批評ループ: 品質が十分なら exit_loop、不十分なら指摘 → 改善を繰り返す。
critic = LlmAgent(
    name="critic",
    model=MODEL,
    description="レポートの品質を評価し、十分なら停止を指示する。",
    instruction=(
        "次のレポートを、網羅性と明確さの観点で評価してください。十分な品質なら"
        " exit_loop ツールを呼んでループを終了します。改善余地があれば、具体的な"
        "指摘を 2 点までに絞って述べてください。\n\nレポート:\n{report}"
    ),
    tools=[exit_loop],
    output_key="feedback",
)

reviser = LlmAgent(
    name="reviser",
    model=MODEL,
    description="指摘に基づきレポートを改善する。",
    instruction=(
        "次のレポートを、指摘に従って改善し、レポート全文を出力してください。\n\n"
        "レポート:\n{report}\n\n指摘:\n{feedback?}"
    ),
    output_key="report",
)

critic_loop = LoopAgent(
    name="critic_loop",
    max_iterations=2,
    sub_agents=[critic, reviser],
)
