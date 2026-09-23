# =====================================================================
# M7 ― Multi-Agent Orchestration
# ---------------------------------------------------------------------
# ■ 前回（M6）から引き継ぐもの
#   state（output_key）で結果を受け渡すという考え方。
# ■ 今回足すもの
#   Code 1. billing / shipping / returns の 3 体（specialists.py）
#   Code 2. SequentialAgent … 順番に実行する
#   Code 3. LoopAgent       … 条件を満たすまで繰り返す
#   Code 4. ParallelAgent   … 同時に実行する
#   Code 5. どれを選ぶか    … 判断フロー（このファイルの末尾）
#
# ⚠️ 先に言っておくこと（講師ガイドの指示どおり Code 2 の時点で 1 回だけ）
#   SequentialAgent / ParallelAgent / LoopAgent は ADK 2.0 で「非推奨」。
#   ・インスタンス化すると DeprecationWarning が出るが、動作はする
#   ・「どの形を選ぶか」という考え方はそのまま生きる
#   ・新しい書き方（Workflow グラフ）への書き換えは M8 で行う
#     （対応表は workflow_equivalents.py）
# =====================================================================

import os

from google.adk import Agent

# 【非推奨】資料の書き方（ADK 1.x からのテンプレート agent）
from google.adk.agents.loop_agent import LoopAgent
from google.adk.agents.parallel_agent import ParallelAgent
from google.adk.agents.sequential_agent import SequentialAgent
from google.adk.tools import exit_loop

from .specialists import billing_agent, returns_agent, shipping_agent

MODEL = os.environ.get("GEMINI_MODEL", "gemini-flash-latest")


# =====================================================================
# Code 2. SequentialAgent ― 順番に実行する
# ---------------------------------------------------------------------
#   Input ──▶ validate ──▶ pricing ──▶ confirm ──▶ Output
#
# sub_agents のリスト順に実行される。前の agent の結果は
# output_key で state に書き、次の agent が {キー} で読む。
# =====================================================================
validate_agent = Agent(
    name="validate_agent",
    model=MODEL,
    instruction="Check that the customer's order request names a product and a quantity. "
    "Reply with the normalized request, or 'INVALID' with a reason.",
    output_key="validated_order",
)
pricing_agent = Agent(
    name="pricing_agent",
    model=MODEL,
    instruction="Estimate a price for this validated order: {validated_order}. "
    "Assume USD 10 per unit.",
    output_key="priced_order",
)
confirm_agent = Agent(
    name="confirm_agent",
    model=MODEL,
    instruction="Write a one-paragraph order confirmation for the customer based on: {priced_order}",
)

order_pipeline = SequentialAgent(
    name="order_pipeline",
    sub_agents=[validate_agent, pricing_agent, confirm_agent],
)


# =====================================================================
# Code 3. LoopAgent ― 条件を満たすまで繰り返す
# ---------------------------------------------------------------------
#        ┌──────────────────────────────┐
#        ▼                              │
#   draft_agent ──▶ quality_agent ──────┘（合格なら exit_loop で脱出）
#
# ・max_iterations は「保険」。脱出条件が永遠に満たされない場合に止める。
# ・ループを抜ける合図は組み込み tool の exit_loop
#   （中身は tool_context.actions.escalate = True。M5 の Flow control）
# =====================================================================
draft_agent = Agent(
    name="draft_agent",
    model=MODEL,
    instruction="Write (or improve) a short reply to the customer's complaint. "
    "Previous feedback, if any: {review_feedback?}",
    output_key="draft_reply",
)
quality_agent = Agent(
    name="quality_agent",
    model=MODEL,
    instruction="""Review this draft reply: {draft_reply}
If it is polite, specific, and under 80 words, call the `exit_loop` tool.
Otherwise reply with one sentence of concrete feedback.""",
    tools=[exit_loop],
    output_key="review_feedback",
)

refine_loop = LoopAgent(
    name="response_refiner",
    sub_agents=[draft_agent, quality_agent],
    max_iterations=5,  # 保守的に。上限に達したら最後の draft で終了する
)


# =====================================================================
# Code 4. ParallelAgent ― 同時に実行する
# ---------------------------------------------------------------------
#          ┌──▶ inventory  ──▶ inventory_info ─┐
#  Input ──┼──▶ promotions ──▶ promotions_info ┼──▶ gather
#          └──▶ account    ──▶ account_info ───┘
#
# ・子どうしは互いの結果を見られない（独立したタスク向け）
# ・各子が「別々の output_key」に書き、後段の gather で統合する
#   → ParallelAgent 単体では統合しないので、SequentialAgent で包む
# =====================================================================
inventory_agent = Agent(
    name="inventory_agent",
    model=MODEL,
    instruction="Say whether the requested product is in stock (assume yes).",
    output_key="inventory_info",
)
promotions_agent = Agent(
    name="promotions_agent",
    model=MODEL,
    instruction="Mention one current promotion (invent a plausible one).",
    output_key="promotions_info",
)
account_agent = Agent(
    name="account_agent",
    model=MODEL,
    instruction="Say the customer is a member in good standing.",
    output_key="account_info",
)

lookup_parallel = ParallelAgent(
    name="account_lookup",
    sub_agents=[inventory_agent, promotions_agent, account_agent],
)
lookup_gather = Agent(
    name="lookup_gather",
    model=MODEL,
    instruction="Combine into one reply: {inventory_info} / {promotions_info} / {account_info}",
)
lookup_pipeline = SequentialAgent(
    name="lookup_pipeline", sub_agents=[lookup_parallel, lookup_gather]
)


# =====================================================================
# 通し題材（root_agent）：3 体の specialist を並列に動かして 1 つの返答にする
# ---------------------------------------------------------------------
#          ┌──▶ billing_agent  ─▶ state["billing_response"]  ─┐
#  質問 ───┼──▶ shipping_agent ─▶ state["shipping_response"] ─┼──▶ support_summary
#          └──▶ returns_agent  ─▶ state["returns_response"]  ─┘
#
# 例：「A-1001 の残高と、注文 O-5001 がいつ届くか教えて」
# 課題：関係ない specialist まで毎回動く（"N/A" を返すだけでもコストがかかる）
#   → M8 では classifier が「必要な specialist だけ」を選んで発火させる
# =====================================================================
support_summary = Agent(
    name="support_summary",
    model=MODEL,
    instruction="""Combine the specialist answers into one reply to the customer.
Ignore any answer that is "N/A".

Billing: {billing_response?}
Shipping: {shipping_response?}
Returns: {returns_response?}
""",
)

root_agent = SequentialAgent(
    name="support_pipeline",
    sub_agents=[
        ParallelAgent(
            name="specialists", sub_agents=[billing_agent, shipping_agent, returns_agent]
        ),
        support_summary,
    ],
)

# 他のテンプレートを adk web で試すときは、右辺を差し替える：
# root_agent = order_pipeline   # Code 2
# root_agent = refine_loop      # Code 3
# root_agent = lookup_pipeline  # Code 4


# =====================================================================
# Code 5. どれを選ぶか ― 判断フロー
# ---------------------------------------------------------------------
#  タスクの順序は重要か
#    │ yes ──▶ SequentialAgent（条件分岐や非線形フローも要るなら Workflow）
#    │ no
#    ▼
#  タスクは互いに独立しているか
#    │ yes ──▶ ParallelAgent ＋ gather ステップ
#    │ no
#    ▼
#  出力は複数回の反復で改善する必要があるか
#    │ yes ──▶ LoopAgent（max_iterations は保守的に）
#    │ no
#    ▼
#  ルーティングにモデルの推論が必要か
#    │ yes ──▶ sub_agents を持つ Agent（M9）
#    │         または明示的なグラフルーティング（M8）
#    │ no
#    ▼
#  複雑な制御フロー ──▶ ADK 2.0 Workflow（M8）
# =====================================================================
