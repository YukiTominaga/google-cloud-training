# =====================================================================
# M8 で使う specialist（Workflow のノード版）
# ---------------------------------------------------------------------
# M7 の specialists.py との違いは 2 点だけです。
#   1. mode="single_turn" を付ける
#      ADK 2.9.2 では、グラフのノードとして使う Agent は single_turn が正解。
#      （collaborative / task モードはグラフ内では無効化されている。
#        構築時にはエラーにならず、実行して初めて挙動の違いに気づくので注意）
#   2. output_key が不要になる
#      Workflow では各ノードの出力が「辺」に沿って次のノードへ渡り、
#      JoinNode がノード名をキーにまとめてくれるため、state を経由しない。
#
# 同じ Agent インスタンスは 1 つのグラフにしか所属できないので、
# 複数の Workflow（examples.py）で使い回せるよう「作る関数」にしている。
# =====================================================================

import os

from google.adk import Agent

from .tools import (
    check_return_policy,
    get_delivery_estimate,
    initiate_return,
    list_invoices,
    lookup_account,
    lookup_order,
    track_order,
)

MODEL = os.environ.get("GEMINI_MODEL", "gemini-flash-latest")


def make_billing_agent() -> Agent:
    return Agent(
        name="billing_agent",
        model=MODEL,
        description="Answers billing and payment questions: balances, invoices, charges.",
        instruction="""あなたは請求担当の specialist です。
サポートチケットを受け取ります。アカウント ID（例: A-1001）が書かれていれば
`lookup_account` を呼び出し、成功した場合に限り `list_invoices` を呼び出してください。
アカウント ID が無ければ、1 文で顧客に尋ねてください。
tool から得たもの以外の数値は決して答えないでください。""",
        tools=[lookup_account, list_invoices],
        mode="single_turn",
    )


def make_shipping_agent() -> Agent:
    return Agent(
        name="shipping_agent",
        model=MODEL,
        description="Looks up order status and estimated delivery dates.",
        instruction="""あなたは配送担当の specialist です。
注文 ID が書かれたサポートチケットを受け取ります。現在の状況は `track_order` で、
到着予定日は `get_delivery_estimate` で調べてください。""",
        tools=[track_order, get_delivery_estimate],
        mode="single_turn",
    )


def make_returns_agent() -> Agent:
    return Agent(
        name="returns_agent",
        model=MODEL,
        description="Processes customer return requests and checks return policy.",
        instruction="""あなたは返品担当の specialist です。
注文 ID が書かれたサポートチケットを受け取ります。`lookup_order` を呼び出し、次に
`check_return_policy` を呼び出してください。返品対象の場合に限り、`initiate_return` を
呼び出して RMA ID を伝えてください。""",
        tools=[lookup_order, check_return_policy, initiate_return],
        mode="single_turn",
    )


# agent.py（通し題材）で使うインスタンス
billing_agent = make_billing_agent()
shipping_agent = make_shipping_agent()
returns_agent = make_returns_agent()
