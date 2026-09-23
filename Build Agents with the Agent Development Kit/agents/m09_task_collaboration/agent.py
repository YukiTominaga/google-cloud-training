# =====================================================================
# M9 ― Task-Based Collaboration
# Code 6. 通し題材 ― coordinator を被せた完成形
# ---------------------------------------------------------------------
# ■ 前回（M8）から引き継ぐもの
#   billing / shipping / returns の 3 体と、Pydantic で型を付ける考え方。
# ■ 今回足すもの
#   M8 は「開発者がグラフで経路を決める」方式だった。
#   M9 は「coordinator（LLM）が description を読んで委譲先を決める」方式。
#   委譲のされ方は、子 agent 側の mode で制御する。
#
#   mode           | ユーザーと対話するか | 向いている仕事
#   ---------------+----------------------+---------------------------------
#   （指定なし）   | する（会話ごと移る） | 従来の transfer。制御を丸ごと渡す
#   "task"         | する（必要な分だけ） | 返品受付のように、足りない情報を
#                  |                      | ユーザーに聞き返しながら進める仕事
#   "single_turn"  | しない（完全自律）   | 残高照会のように、入力だけで
#                  |                      | 完結して結果を返せる仕事
#
# ■ delegation の流れ（Code 4）
#   ユーザー
#     │
#     ▼
#   support_coordinator ──┬──▶ billing_agent   (single_turn) ─┐ 並列
#                         ├──▶ shipping_agent  (single_turn) ─┤
#                         └──▶ returns_agent   (task) ────────┤ 順次（必要ならユーザーに質問）
#                                                             ▼
#                                                   統合されたレスポンス
#
#   トレースでの見え方（google-adk 2.9.2 で確認）：
#     single_turn / task の子は、coordinator からは「agent 名の tool」に見える。
#       billing_agent(request="...")   ← single_turn は request 文字列 1 つ
#       returns_agent(order_id="...")  ← task は input_schema がそのまま引数になる
#     子の output_schema の JSON が、その tool の結果として coordinator に返る。
#
#   task モードの子が仕事を終えて親に戻るとき、ADK が自動で用意する
#   内部 tool「finish_task」が呼ばれる。トレースビューにこの名前が出たら
#   「specialist が仕事を終えて coordinator に戻った」印。
#
#   Code 5（AgentTool）の例は agent_tool_example.py にあります。
#   3 つの mode を見比べるには、adk web で m09_task_collaboration_chat / _task /
#   _single_turn を選ぶ（組み立て方と比較用プロンプトは mode_variants.py）。
#
# ■ 試すプロンプト（adk web / adk run で入力）
#   1. 「A-1001 の残高と、注文 O-5001 の配達予定日を教えて」
#      → coordinator が billing_agent(request=...) と shipping_agent(request=...) を
#        tool として呼び、BillingResult / ShippingResult の JSON を受け取ってまとめる
#   2. 「返品したいです」→ 聞き返されたら「O-5002 です。サイズが合いませんでした」
#      → returns_agent（task）が注文 ID と理由を聞き返し、lookup_order →
#        check_return_policy → initiate_return の後、finish_task で coordinator に戻る
#   3. 「注文 O-5003 を返品したい。気が変わった」
#      → O-5003 は処理中（processing）なので check_return_policy が eligible false を返し、
#        initiate_return は呼ばれない
#   4. 「A-9999 の残高を教えて」
#      → billing_agent の lookup_account が "error"（存在しないアカウント）を返す
# =====================================================================

import os

from google.adk import Agent
from pydantic import BaseModel, Field

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


# =====================================================================
# 委譲の「契約」＝ 入出力のスキーマ
# ---------------------------------------------------------------------
# ・output_schema：子が親に返す結果の形。親は自由文ではなく
#   構造化された結果を受け取るので、複数の子の結果を確実に統合できる。
# ・input_schema ：子が仕事を始めるのに必要な入力（task モードで使う）。
#   Field(description=...) は「何を集めればよいか」のモデル向け説明。
# =====================================================================
class BillingResult(BaseModel):
    balance: float = Field(description="Current balance in USD.")
    summary: str = Field(description="One sentence for the customer.")


class ShippingResult(BaseModel):
    status: str = Field(description="Current order status.")
    eta: str = Field(description="Estimated delivery date, YYYY-MM-DD.")


class ReturnRequest(BaseModel):
    order_id: str = Field(description="The order the customer wants to return.")


class ReturnResult(BaseModel):
    rma_id: str = Field(description="The return authorization ID that was issued.")
    summary: str = Field(description="One sentence describing what was arranged.")


# =====================================================================
# Code 3. Single Turn モード ― 完全に自律的な delegation
# ---------------------------------------------------------------------
# ユーザーには一切話しかけず、1 回の実行で結果（output_schema）を返す。
# 互いに独立しているので、coordinator は billing と shipping を並列に呼べる。
# =====================================================================
billing_agent = Agent(
    name="billing_agent",
    model=MODEL,
    mode="single_turn",
    output_schema=BillingResult,
    description="Retrieves account balance, invoices, and payment history.",
    instruction="アカウントを照会し、請求状況を要約してください。",
    tools=[lookup_account, list_invoices],
)

shipping_agent = Agent(
    name="shipping_agent",
    model=MODEL,
    mode="single_turn",
    output_schema=ShippingResult,
    description="Looks up order status and estimated delivery dates.",
    instruction="注文を照会し、現在どこにあるかを要約してください。",
    tools=[track_order, get_delivery_estimate],
)


# =====================================================================
# Code 2. Task モード ― スコープが定義された対話的な delegation
# ---------------------------------------------------------------------
# 返品は「注文番号」「理由」が揃わないと進められない。
# task モードの子は、足りない情報をユーザーに聞き返しながら仕事を進め、
# 終わったら ReturnResult を持って coordinator に戻る（finish_task）。
# 会話を丸ごと渡す従来の transfer と違い、「スコープが決まった仕事」
# だけを引き受けて、終わったら必ず親に制御が戻るのがポイント。
# =====================================================================
returns_agent = Agent(
    name="returns_agent",
    model=MODEL,
    mode="task",
    input_schema=ReturnRequest,
    output_schema=ReturnResult,
    description="Processes customer return requests and checks return policy.",
    instruction=(
        "注文 ID と返品理由を聞き取ってください。返品ポリシーが適用されることを"
        "確認してください。結果は構造化された ReturnResult で返してください。"
    ),
    tools=[lookup_order, check_return_policy, initiate_return],
)


# =====================================================================
# Code 1. coordinator の骨格 ＋ Code 6 の instruction
# ---------------------------------------------------------------------
# ・sub_agents に子を並べると、coordinator は各子の description を読んで
#   委譲先を選ぶ（M1 で張った「description は看板」の伏線の回収）。
# ・「自分では答えない、必ず委譲する」と instruction に書いておかないと、
#   coordinator がもっともらしい数字を自分で答えてしまう。
# ・1 つの agent は 1 つの親しか持てない（同じ billing_agent を
#   2 つの coordinator の sub_agents に入れるとエラー）。
#   複数の親から使いたいときは AgentTool（agent_tool_example.py）。
# =====================================================================
root_agent = Agent(
    name="support_coordinator",
    model=MODEL,
    description="Routes customer support requests to the right specialist.",
    instruction="""あなたはオンライン小売店のカスタマーサポート窓口として、問い合わせを振り分けます。

委譲先:
- 残高・請求書・請求額       -> billing_agent
- 注文状況・配達予定日       -> shipping_agent
- 返品・返金                 -> returns_agent

1 つのメッセージが複数の領域にまたがる場合は、該当する各専門 agent に委譲し、
それぞれの構造化された結果を 1 つの返答にまとめてください。
事実に関する質問には決して自分で答えず、必ず委譲してください。
""",
    sub_agents=[billing_agent, shipping_agent, returns_agent],
)
