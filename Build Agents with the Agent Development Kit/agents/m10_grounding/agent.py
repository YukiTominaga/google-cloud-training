# =====================================================================
# M10 ― Grounding and Enterprise Data Integration
# Code 6. 通し題材 ― サポート agent を社内データに繋ぐ
# ---------------------------------------------------------------------
# ■ 前回（M9）から引き継ぐもの
#   coordinator ＋ specialist の構成。tool の作法（M4/M5）。
# ■ 今回足すもの
#   ダミーデータの代わりに、社内の「本物のデータ」に grounding する。
#     Code 1. .env の切り替え               → .env.example
#     Code 2. 非構造化：google_search / VertexAiSearchTool → research_agents.py
#     Code 3. 構造化：カスタム function tool → structured_data.py
#     Code 4. ルーティング（山場）          → routing.py
#     Code 5. MCP                           → mcp_examples.py
#
# ■ このファイルを実際に動かすには（Cloud 環境が必要）
#   1. m10_grounding/.env を用意する（.env.example 参照）
#   2. POLICY_DATASTORE の PROJECT を自分のプロジェクト ID に置き換え、
#      Agent Search にデータストア「support-policies」を作っておく
#   3. 社内の MCP サーバー URL を置き換える
#   Cloud 環境なしで試したいときは、末尾の root_agent を
#   routing.retrieval_router に差し替える（API キーだけで動く）。
#
# ■ 試すプロンプト（adk web / adk run で入力）
#   ※ API キーだけで試す前提。末尾の root_agent を routing.retrieval_router に
#     差し替えてから入力する（grounded_support_agent は Cloud 環境が必要）。
#     ダミー文書は英語で、search_documents_tool は単純なキーワード一致なので、
#     英語のキーワードを添えると当たりやすい。
#   1. 「返品（return）は何日以内ならできますか？」
#      → search_documents_tool が呼ばれ、return-policy.md の一節が引用される
#   2. 「A-1001 の最近の注文を見せて」
#      → sql_query_tool（query_orders）が呼ばれるが、adk web では state に
#        session_user_id が無いため "denied" が返る（tool 内の認可が効く様子）
#   3. 「A-1001 の注文 O-5002 は返品（return）できますか？」
#      → sql_query_tool と search_documents_tool の両方が呼ばれることをトレースで確認
#   4. 「ギフトラッピング（gift wrapping）はできますか？」
#      → search_documents_tool が "not_found" を返し、推測せずにその旨を伝えるかを見る
#        （モデルが query に policy などを足すと別の文書に当たることもある）
# =====================================================================

import os

from google.adk import Agent
from google.adk.tools import VertexAiSearchTool
from google.adk.tools.google_search_tool import GoogleSearchTool
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams

# .env の GEMINI_MODEL で差し替え可能
MODEL = os.environ.get("GEMINI_MODEL", "gemini-flash-latest")

# ---------------------------------------------------------------------
# 社内の規程文書を入れた Agent Search のデータストア
# ---------------------------------------------------------------------
POLICY_DATASTORE = (
    "projects/PROJECT/locations/global/collections/default_collection/dataStores/support-policies"
)

# ---------------------------------------------------------------------
# 社内の注文管理システムを MCP 経由で
# ---------------------------------------------------------------------
orders_toolset = McpToolset(
    connection_params=StreamableHTTPConnectionParams(
        url="https://internal-tools.example.com/mcp",
    ),
    tool_filter=["get_order", "get_shipment_status"],  # 参照系だけ
)

# ---------------------------------------------------------------------
# ⚠️ 検索 tool と function calling を同居させる：bypass_multi_tools_limit=True
# ---------------------------------------------------------------------
# Gemini API は「組み込みの検索 tool（google_search / VertexAiSearchTool）」と
# 「function calling（MCP の tool や関数 tool）」を 1 つのリクエストに
# 同居させられない。そのまま 3 つを 1 つの agent に並べると、
# 実行時に Gemini API 側でエラーになる。
#
# ADK 2.9.2 ではコンストラクタに bypass_multi_tools_limit=True を渡すと、
# ADK が自動で次のように置き換えて同居できるようにしてくれる。
#   google_search      → 検索専用の子 agent を AgentTool で包んだもの
#   VertexAiSearchTool → 同じデータストアを引く DiscoveryEngineSearchTool
# （モジュール変数 google_search は bypass なしのインスタンスなので、
#   ここでは GoogleSearchTool を自分で作っている）
policy_search = VertexAiSearchTool(
    data_store_id=POLICY_DATASTORE,
    bypass_multi_tools_limit=True,
)
web_search = GoogleSearchTool(bypass_multi_tools_limit=True)

grounded_support_agent = Agent(
    name="grounded_support_agent",
    model=MODEL,
    description="Answers support questions grounded in policies and order data.",
    instruction="""あなたはオンライン小売店のカスタマーサポート agent です。

使い分け:
- 返品ポリシー・保証・配送ルール           -> 社内文書検索 tool
- 注文状況・配送追跡                       -> get_order / get_shipment_status
- 公開情報（運送会社の障害情報、
  祝日の営業スケジュールなど）             -> google_search

ルール:
- tool で答えを得られる事実に関する質問には、記憶で答えないでください。
- どの tool も結果を返さなかった場合は、推測せずにその旨を伝えてください。
- 根拠にしたポリシー文書を必ず引用してください。
""",
    tools=[
        policy_search,  # 非構造化・社内
        web_search,  # 非構造化・公開
        orders_toolset,  # 構造化・社内（MCP）
    ],
)

root_agent = grounded_support_agent

# Cloud 環境なしで試す場合：
# from .routing import retrieval_router
# root_agent = retrieval_router
