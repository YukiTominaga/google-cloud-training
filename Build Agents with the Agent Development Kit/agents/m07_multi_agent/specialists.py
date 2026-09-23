# =====================================================================
# M7 Code 1. 3 体の specialist ― 通し題材が 1 体から 3 体になる
# ---------------------------------------------------------------------
# ■ 見せたいポイント
#   1. description が「外から見た看板」になる（M1 で張った伏線の回収）。
#      親 agent はこの 1 行を読んで「どの子に渡すか」を決める。
#      → 3 体の description が互いに重ならないように書く。
#   2. output_key を agent ごとに分ける。
#      並べて実行したとき、結果が state の別々のキーに残るので
#      後段の agent（gather / summary）がまとめて読める。
#   3. name はトレース上で「誰が喋ったか」を見分ける鍵。
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

# .env の GEMINI_MODEL で差し替え可能
MODEL = os.environ.get("GEMINI_MODEL", "gemini-flash-latest")

billing_agent = Agent(
    name="billing_agent",
    model=MODEL,
    description="Answers billing and payment questions: balances, invoices, charges.",
    instruction="""You are a billing specialist.
Always call `lookup_account` first. Only if it succeeds, call `list_invoices`.
Never state a figure that did not come from a tool.
If the message has no billing question, reply with "N/A".""",
    tools=[lookup_account, list_invoices],
    output_key="billing_response",  # → state["billing_response"]
)

shipping_agent = Agent(
    name="shipping_agent",
    model=MODEL,
    description="Looks up order status and estimated delivery dates.",
    instruction="""You are a shipping specialist.
Use `track_order` for the current status and `get_delivery_estimate` for the ETA.
If the message has no shipping question, reply with "N/A".""",
    tools=[track_order, get_delivery_estimate],
    output_key="shipping_response",  # → state["shipping_response"]
)

returns_agent = Agent(
    name="returns_agent",
    model=MODEL,
    description="Processes customer return requests and checks return policy.",
    instruction="""You are a returns specialist.
Call `lookup_order`, then `check_return_policy`. Only if the order is eligible,
call `initiate_return` and share the RMA ID.
If the message has no return request, reply with "N/A".""",
    tools=[lookup_order, check_return_policy, initiate_return],
    output_key="returns_response",  # → state["returns_response"]
)
