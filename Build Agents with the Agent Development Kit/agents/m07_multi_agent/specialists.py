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
    instruction="""あなたは請求担当の specialist です。
必ず最初に `lookup_account` を呼び出してください。成功した場合に限り `list_invoices` を呼び出してください。
tool から得たもの以外の数値は決して答えないでください。
メッセージに請求に関する質問が含まれていなければ "N/A" とだけ返してください。""",
    tools=[lookup_account, list_invoices],
    output_key="billing_response",  # → state["billing_response"]
)

shipping_agent = Agent(
    name="shipping_agent",
    model=MODEL,
    description="Looks up order status and estimated delivery dates.",
    instruction="""あなたは配送担当の specialist です。
現在の状況は `track_order` で、到着予定日は `get_delivery_estimate` で調べてください。
メッセージに配送に関する質問が含まれていなければ "N/A" とだけ返してください。""",
    tools=[track_order, get_delivery_estimate],
    output_key="shipping_response",  # → state["shipping_response"]
)

returns_agent = Agent(
    name="returns_agent",
    model=MODEL,
    description="Processes customer return requests and checks return policy.",
    instruction="""あなたは返品担当の specialist です。
`lookup_order` を呼び出し、次に `check_return_policy` を呼び出してください。注文が返品対象の場合に限り、
`initiate_return` を呼び出して RMA ID を伝えてください。
メッセージに返品の依頼が含まれていなければ "N/A" とだけ返してください。""",
    tools=[lookup_order, check_return_policy, initiate_return],
    output_key="returns_response",  # → state["returns_response"]
)
