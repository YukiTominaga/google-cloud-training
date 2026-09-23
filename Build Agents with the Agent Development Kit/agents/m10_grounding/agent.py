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
# ⚠️ 講師ガイド Code 6 からの変更点：bypass_multi_tools_limit=True
# ---------------------------------------------------------------------
# Gemini API は「組み込みの検索 tool（google_search / VertexAiSearchTool）」と
# 「function calling（MCP の tool や関数 tool）」を 1 つのリクエストに
# 同居させられない。ガイドのように 3 つを 1 つの agent に並べると、
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
    instruction="""You are a customer support agent for an online retailer.

Routing:
- Return policy, warranty, shipping rules  -> the internal document search tool.
- Order status, shipment tracking          -> get_order / get_shipment_status.
- Public information (carrier outages,
  holiday schedules)                       -> google_search.

Rules:
- Never answer a factual question from memory if a tool can supply the answer.
- If no tool returns a result, say so rather than estimating.
- Always cite the policy document you relied on.
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
