# =====================================================================
# M11 ― Gemini Enterprise Agent Platform
# ---------------------------------------------------------------------
# ■ 前回（M10）から引き継ぐもの
#   社内データに grounding したサポート agent。
# ■ このモジュールの 1 点
#   「ローカルからプラットフォームへ移るとき、差し替えるのは runner だけ」
#   agent のコード（このファイル）は 1 行も変えない。
#   変わるのは Runner に渡す session_service / memory_service だけ
#   → runners.py、コマンド版は run_commands.sh。
#
# ■ 素材 1〜2, 4〜5（概念）の要点
#   4 つの柱：Build（ADK / Agent Studio）/ Scale（Agent Runtime /
#             Sessions / Memory Bank / Sandbox）/ Govern（Identity /
#             Gateway / Registry / Model Armor）/ Optimize（Evaluation 等）
#   Agent Sessions   … 短期記憶（いまの会話の流れ）
#   Agent Memory Bank … 長期記憶（ユーザーの嗜好や事実を数週間〜数か月）
#   runtime の選択：統合の容易さ → Agent Runtime / コンテナ → Cloud Run /
#                   完全な制御と価格 → GKE（サービスレイヤはどこからでも使える）
#
# ■ 改称について（Code 3 の前に必ず触れる）
#   製品名は「Vertex AI …」から「… on Gemini Enterprise Agent Platform」に
#   改称されたが、クラス名（VertexAiSessionService など）とリソース種別
#   （reasoningEngine）は旧名のまま。コードが古いわけではない。
#
# ■ 試すプロンプト（adk web / adk run で入力）
#   ※ adk web の既定の memory は InMemoryMemoryService（プロセス内・キーワード一致）。
#     adk web を再起動すると記憶は消える。Memory Bank で試すには run_commands.sh の
#     --memory_service_uri か、runners.py の platform モード（AGENT_ENGINE_ID が必要）を使う。
#   1. 「私のアカウント ID は A-1001 です。覚えておいてください。」
#      → 最初に load_memory が呼ばれる（まだ何も見つからない）。実行後に
#        after_agent_callback がこの session を memory に保存する
#   2. （New Session で新しいセッションにしてから）「私の残高はいくらですか？」
#      → load_memory が前のセッションの A-1001 を見つけ、lookup_account が呼ばれる
#        （runners.py のデモと同じ流れ）
#   3. 「A-1001 の請求書を見せて」
#      → lookup_account → list_invoices の順に呼ばれる
#   4. 「注文 O-5002 はいつ届きますか？」
#      → O-5002 は配達済みのため get_delivery_estimate が "error" を返す。
#        到着予定日をでっち上げないかを見る
# =====================================================================

import os
from typing import Optional

from google.adk import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.tools import load_memory
from google.genai import types

from .tools import get_delivery_estimate, list_invoices, lookup_account, track_order

# .env の GEMINI_MODEL で差し替え可能
MODEL = os.environ.get("GEMINI_MODEL", "gemini-flash-latest")


# ---------------------------------------------------------------------
# 会話を長期記憶（Memory Bank）に保存する callback
# ---------------------------------------------------------------------
# load_memory は「保存済みの記憶を検索する」tool なので、
# 誰かが会話を記憶に入れておかないと何も見つからない。
# ここでは agent の実行が終わるたびに、その session を memory service に渡す。
#   ・ローカル（adk web の既定）… InMemoryMemoryService（キーワード一致・プロセス内だけ）
#   ・プラットフォーム          … VertexAiMemoryBankService（LLM が事実を抽出して長期保存）
# どちらでもこのコードは同じ。差し替わるのは runner 側。
async def save_session_to_memory(callback_context: CallbackContext) -> Optional[types.Content]:
    await callback_context.add_session_to_memory()
    return None


# ---------------------------------------------------------------------
# Code 3（末尾）. load_memory で「前回言われたこと」を思い出す
# ---------------------------------------------------------------------
root_agent = Agent(
    name="support_coordinator",
    model=MODEL,
    description="Answers billing and shipping questions and remembers returning customers.",
    instruction="""あなたはオンライン小売店のカスタマーサポート agent です。
会話の最初に load_memory を使い、この顧客が以前伝えてくれた内容
（アカウント ID や好みなど）を思い出してください。
請求には lookup_account / list_invoices を、配送には track_order /
get_delivery_estimate を使ってください。tool から得ていない数値は決して伝えないでください。""",
    tools=[load_memory, lookup_account, list_invoices, track_order, get_delivery_estimate],
    after_agent_callback=save_session_to_memory,
)
