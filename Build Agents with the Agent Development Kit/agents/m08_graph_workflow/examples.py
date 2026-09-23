# =====================================================================
# M8 Code 1〜5. Workflow の部品を 1 つずつ見せる例
# ---------------------------------------------------------------------
# スライドで順番に見せるための単独の例です（adk web には読み込まれません）。
# 同じ Agent インスタンスは 1 つのグラフにしか所属できないので、
# 例ごとに specialists.make_*() で新しく作っています。
# =====================================================================

import os

from google.adk import Agent, Event, Workflow
from google.adk.workflow import DEFAULT_ROUTE, JoinNode
from pydantic import BaseModel

from .specialists import make_billing_agent, make_returns_agent, make_shipping_agent

MODEL = os.environ.get("GEMINI_MODEL", "gemini-flash-latest")


def make_classifier() -> Agent:
    """メッセージを BILLING / SHIPPING / RETURNS の 1 語に分類する LLM ノード。"""
    return Agent(
        name="classifier",
        model=MODEL,
        instruction=(
            "顧客のメッセージを BILLING, SHIPPING, RETURNS のうち"
            "ちょうど 1 つに分類してください。ラベルだけを返してください。"
        ),
        # ⚠️ グラフのノードとして使う Agent は mode="single_turn"。
        #    指定しなくても構築時にはエラーにならず、実行して初めて
        #    挙動の違いに気づくので、ここは必ず口に出して強調する。
        mode="single_turn",
    )


# ---------------------------------------------------------------------
# [関数ノード] router：分類ラベル（文字列）を route シグナルに変換する
# ---------------------------------------------------------------------
def router(node_input: str):
    """分類ラベルを route シグナルに変換する。"""
    # node_input には直前のノード（classifier）の出力がそのまま入ってくる
    return Event(route=node_input.strip())


# =====================================================================
# Code 1. 最小の graph
# ---------------------------------------------------------------------
# Workflow は「辺（edge）のリスト」で定義する。
# ("START", classifier, router) は START → classifier → router の逐次チェーン。
# router の先に辺が無いので、router が終わった時点で workflow も終わる。
# =====================================================================
minimal_workflow = Workflow(
    name="support_workflow_minimal",
    edges=[
        ("START", make_classifier(), router),
    ],
)


# =====================================================================
# Code 2. 条件分岐によるルーティング
# ---------------------------------------------------------------------
# (router, {ラベル: ノード}) と書くと、router が返した
# Event(route="BILLING") の値と dict のキーが照合され、一致した先だけが動く。
#   LLM（classifier）は「判断」、関数（router）は「振り分け」と役割を分ける。
# =====================================================================
routing_workflow = Workflow(
    name="support_workflow_routing",
    edges=[
        ("START", make_classifier(), router),
        (
            router,
            {
                "BILLING": make_billing_agent(),
                "SHIPPING": make_shipping_agent(),
                "RETURNS": make_returns_agent(),
            },
        ),
    ],
)


# =====================================================================
# Code 3. DEFAULT_ROUTE と route のリスト
# ---------------------------------------------------------------------
# ① DEFAULT_ROUTE：どのキーにも一致しなかったときの行き先。
#    LLM は「BILLING.」「billing」「I think BILLING」のように揺れるので、
#    LLM を分類器に使う以上、事実上必須。
# ② route にリストを渡すと、複数の分岐が「同時に」発火する。
# =====================================================================
def make_fallback_agent() -> Agent:
    return Agent(
        name="fallback_agent",
        model=MODEL,
        instruction="お詫びを述べ、質問を言い換えてもらうよう顧客にお願いしてください。",
        mode="single_turn",
    )


def multi_router(node_input: str):
    """カンマ区切りのラベルをリストにして、該当する分岐をすべて発火させる。"""
    routes = [r.strip() for r in node_input.split(",")]
    return Event(route=routes)  # ["BILLING", "SHIPPING"] など


default_route_workflow = Workflow(
    name="support_workflow_default_route",
    edges=[
        ("START", make_classifier(), multi_router),
        (
            multi_router,
            {
                "BILLING": make_billing_agent(),
                "SHIPPING": make_shipping_agent(),
                "RETURNS": make_returns_agent(),
                DEFAULT_ROUTE: make_fallback_agent(),  # 想定外のラベルはここへ
            },
        ),
    ],
)


# =====================================================================
# Code 4. 並列 fan-out と JoinNode
# ---------------------------------------------------------------------
#                                    ┌──▶ billing_agent  ─┐
#  START ─▶ classifier ─▶ router() ──┼──▶ shipping_agent ─┼──▶ JoinNode ─▶ synthesizer
#                                    └──▶ returns_agent  ─┘
#
# ・同じソース（router）から複数ノードへ「条件なしの辺」を張ると fan-out。
#   条件なしの辺は route の値に関係なく、常に発火する。
# ・JoinNode は「つながっている前段がすべて完了したら」発火し、
#   {"billing_agent": 出力, "shipping_agent": 出力, ...} の形にまとめて渡す。
#   → M7 のように output_key を揃える設計が不要になった。
# ⚠️ JoinNode は前段が“すべて”完了するまで待つ。条件分岐で一部しか
#   発火しない構成と組み合わせると合流しない（agent.py の gate を参照）。
# =====================================================================
# fan-out / join の辺で同じノードを何度も指すので、変数に入れておく
_classifier = make_classifier()
_billing, _shipping, _returns = make_billing_agent(), make_shipping_agent(), make_returns_agent()
_join = JoinNode(name="join")
_synthesizer = Agent(
    name="synthesizer",
    model=MODEL,
    instruction="受け取った specialist の回答を、顧客への 1 つの返信にまとめてください。",
    mode="single_turn",
)

fanout_workflow = Workflow(
    name="multi_category_workflow",
    edges=[
        ("START", _classifier, router),
        (router, _billing),  # 条件なしの辺 ＝ 常に発火
        (router, _shipping),
        (router, _returns),
        (_billing, _join),
        (_shipping, _join),
        (_returns, _join),
        (_join, _synthesizer),
    ],
)


# =====================================================================
# Code 5. node 間のデータの流れ
# ---------------------------------------------------------------------
# ・output_schema：そのノードの「出力の形」を Pydantic で固定する
# ・input_schema ：そのノードが「受け取る入力の形」を宣言する
# 前段の output_schema と後段の input_schema を同じ型にすると、
# 型付きのデータが辺に沿って流れる（文字列のパースが不要になる）。
#
# ⚠️ ガイドの instruction にある "{Ticket.order_id}" は、ADK の
#   instruction テンプレート（state のキーを {key} で埋め込む仕組み）
#   では「有効なキー名ではない」ため置換されず、そのままの文字列で
#   モデルに渡る（2.9.2 で確認）。入力はノードの入力として届くので、
#   instruction では「受け取った Ticket の order_id」と言葉で指示する。
# =====================================================================
class Ticket(BaseModel):
    category: str
    order_id: str


typed_classifier = Agent(
    name="classifier",
    model=MODEL,
    instruction="メッセージを分類し、注文 ID を抜き出してください。",
    output_schema=Ticket,  # 出力の形
    mode="single_turn",
)

typed_billing_agent = Agent(
    name="billing_agent",
    model=MODEL,
    input_schema=Ticket,  # 入力の形（前段の output_schema と揃える）
    instruction="受け取った Ticket の order_id について、請求に関する質問に答えてください。",
    mode="single_turn",
)

typed_workflow = Workflow(
    name="typed_workflow",
    edges=[("START", typed_classifier, typed_billing_agent)],
)
