# =====================================================================
# M9 ― 3 つの mode を比べるための coordinator
# ---------------------------------------------------------------------
# agent.py の完成形は「billing / shipping は single_turn、returns は task」
# と、仕事に合わせて mode を混ぜている。ここでは違いを体感できるように、
# 3 体の specialist を「全員同じ mode」にした coordinator を作る。
# adk web のドロップダウンで次のフォルダを選ぶ（コードの差し替えは不要）。
#
#   m09_task_collaboration_chat        … 全員 mode 指定なし（= "chat"。従来の transfer）
#   m09_task_collaboration_task        … 全員 mode="task"
#   m09_task_collaboration_single_turn … 全員 mode="single_turn"
#
# ■ agent.clone() で mode だけ差し替えない理由
#   ADK は Agent の生成時に、task の子へ finish_task を、親へ「子 agent 名の tool」を
#   tools に追加する。clone() はこの追加済みの tools まで複製してしまうので、
#   mode ごとに Agent を作り直している。
#
# ■ 試すプロンプト（3 つのフォルダで同じものを入力して見比べる）
#   （→ 以降は gemini-flash-latest で 1 回試したときの例。LLM なので毎回同じとは限らない）
#   1. 「返品したいです」→ 聞き返されたら「O-5002 です。サイズが合いませんでした」
#      chat        → transfer_to_agent で returns_agent に会話ごと移り、returns_agent が
#                    直接ユーザーに聞き返す。2 ターン目も returns_agent が受けて
#                    initiate_return まで進める（coordinator には戻らない）
#      task        → coordinator が input_schema の order_id を先に聞き返してから
#                    returns_agent(order_id=...) を呼ぶ。理由は渡されないので、
#                    returns_agent が改めてユーザーに理由を聞き返す
#      single_turn → 同じく coordinator が order_id を聞いて呼ぶが、returns_agent は
#                    聞き返せない。initiate_return を呼ばずに rma_id をでっち上げて
#                    返したことがある（output_schema を埋めることを優先してしまう）
#   2. 「A-1001 の残高と、注文 O-5001 の配達予定日を教えて」
#      chat        → billing / shipping / coordinator の間で transfer_to_agent が往復し、
#                    最後は shipping_agent が注文番号を聞き返して止まった
#      task        → billing_agent(request=...) / shipping_agent(request=...) を tool として呼び、
#                    それぞれ finish_task で結果を返してから coordinator がまとめる
#      single_turn → 2 体を tool として呼び、返ってきた JSON を coordinator がまとめる
# =====================================================================

from typing import Literal

from google.adk import Agent

from .agent import (
    MODEL,
    BillingResult,
    ReturnRequest,
    ReturnResult,
    ShippingResult,
    billing_agent,
    returns_agent,
    root_agent,
    shipping_agent,
)
from .tools import (
    check_return_policy,
    get_delivery_estimate,
    initiate_return,
    list_invoices,
    lookup_account,
    lookup_order,
    track_order,
)

Mode = Literal["chat", "task", "single_turn"]


def build_coordinator(mode: Mode) -> Agent:
    """3 体の specialist を同じ mode にした support_coordinator を作る。"""
    # chat の子はユーザーと直接話すので、親との「契約」である
    # input_schema / output_schema は使わない（付けると返答が JSON になる）。
    use_schema = mode != "chat"

    def specialist(original: Agent, tools, input_schema, output_schema) -> Agent:
        return Agent(
            name=original.name,
            model=MODEL,
            mode=mode,
            input_schema=input_schema if use_schema else None,
            output_schema=output_schema if use_schema else None,
            description=original.description,
            instruction=original.instruction,
            tools=tools,
        )

    return Agent(
        name=root_agent.name,
        model=MODEL,
        description=root_agent.description,
        instruction=root_agent.instruction,
        sub_agents=[
            specialist(billing_agent, [lookup_account, list_invoices], None, BillingResult),
            specialist(shipping_agent, [track_order, get_delivery_estimate], None, ShippingResult),
            specialist(
                returns_agent,
                [lookup_order, check_return_policy, initiate_return],
                ReturnRequest,
                ReturnResult,
            ),
        ],
    )
