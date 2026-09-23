# =====================================================================
# M12 ― Deploying with the ADK CLI and Agents CLI
# デプロイ対象の agent（M9 で完成した coordinator と同じもの）
# ---------------------------------------------------------------------
# ■ 前回（M11）から引き継ぐもの
#   「ローカル = クラウド」。ローカルで動いた root_agent を、そのまま
#   Agent Runtime に載せる。agent のコードは M9 から 1 行も変えていない。
#
# ■ デプロイの単位（Code 1）
#   Agent Runtime
#   └── reasoningEngine（デプロイの単位。API 上の呼び名）
#        └── root_agent            ← このファイルの root_agent
#             ├── billing_agent
#             ├── shipping_agent
#             └── returns_agent
#   呼び名は 3 つあるが同じもの：API = reasoningEngine /
#   SDK = agent_engine / 製品名 = Agent Runtime
#
# ■ このフォルダのファイル
#   agent.py / tools.py / __init__.py … デプロイされる本体
#   requirements.txt                  … Agent Runtime 側でインストールする依存
#   .agent_engine_config.json         … デプロイ設定（非推奨フラグの移行先。Code 3）
#   deploy_adk_cli.sh                 … 経路 A：ADK CLI（Code 2 / 3）
#   deploy_agents_cli.sh              … 経路 B：Agents CLI（Code 4）
#   deploy_sdk.py                     … 経路 C：SDK を直接使う（Code 5）
#   deploy_developer_connect.py       … Git リポジトリから直接デプロイ（Code 6）
#
# ⚠️ デプロイ時には import 文を相対 import（from .tools ...）にしておくこと。
#   Agent Runtime 上ではこのフォルダがパッケージとして読み込まれる。
#
# ■ 試すプロンプト（adk web / adk run で入力）
#   ※ デプロイ前は API キーだけで adk web で動く。デプロイ後は同じプロンプトを
#     Agent Runtime 上の agent に投げ、ローカルと同じ委譲・tool 呼び出しになるかを比べる。
#   1. 「A-1001 の残高を教えて」
#      → billing_agent（single_turn）が tool として呼ばれ、中で lookup_account が動く。
#        BillingResult の JSON が coordinator に返る
#   2. 「A-1001 の残高と、注文 O-5001 の配達予定日を教えて」
#      → billing_agent と shipping_agent の両方に委譲され、結果が 1 つの返答にまとまる
#   3. 「注文を返品したい」
#      → returns_agent（task）が注文 ID と理由を聞き返す。「O-5002、サイズが合わなかった」
#        と答えると lookup_order → check_return_policy → initiate_return と進み、
#        finish_task で coordinator に戻る
#   4. 「注文 O-5001 を返品したい。理由は気が変わったから」
#      → O-5001 は未配達（shipped）なので check_return_policy が eligible: false を返す。
#        initiate_return が呼ばれないことをトレースで確認
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
