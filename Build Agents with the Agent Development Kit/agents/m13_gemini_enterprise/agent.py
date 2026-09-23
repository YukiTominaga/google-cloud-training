# =====================================================================
# M13 ― Surfacing Agents to Users on Gemini Enterprise App
# 素材 7. 通し題材 ― サポート agent を社内に公開する
# ---------------------------------------------------------------------
# ■ コース全体のライフサイクル（素材 6）
#   Build（M1〜M10）→ Deploy（M11〜M12）→ Register（M13）→ Share（M13）
#   デプロイしただけの reasoningEngine は、まだ誰にも使われていない。
#   Gemini Enterprise app に「登録」して初めて、社内ユーザーの画面に現れる。
#
# ■ このフォルダのファイル
#   agent.py / tools.py          … 公開する agent（M12 と同じ構成）
#   check_prerequisites.sh       … 素材 1：登録の前提条件の確認
#   register_agent.sh            … 素材 3：API からの登録
#   create_authorization.sh      … 素材 5：OAuth 認可リソースの作成（概略）
#   publish_end_to_end.sh        … 素材 7：Deploy → Register の通し
#   （素材 2 のコンソール登録手順は README を参照）
#
# ■ 素材 4. Description の書き方
#   Gemini Enterprise のルーティングモデルは、登録時の Description を読んで
#   「どの質問をこの agent に回すか」を決める（M1 の「description は看板」の最終回収）。
#     ❌ "社内向けアシスタント"                   … 何を任せてよいか分からない
#     ✅ "Handles order status, billing questions, and return requests for retail
#         customers. Does not handle HR or IT support requests."
#   「何をするか」に加えて「何をしないか」まで書くのがポイント。
#   下の root_agent の description も、登録時の Description と同じ考え方で書く。
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
    # 登録時の Description と同じく「する／しない」を明記した看板
    description=(
        "Handles order status, delivery estimates, billing questions, invoices, "
        "and return requests for retail customers. Does not handle HR, IT "
        "support, or product recommendations."
    ),
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
