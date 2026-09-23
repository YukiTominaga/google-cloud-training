# =====================================================================
# M10 Code 4. ルーティング ― このモジュールの山場
# ---------------------------------------------------------------------
# tool を揃えただけでは、モデルは「どれを使うか」を正しく選べない。
# どの質問を、どの grounding 先に送るかを instruction で明示する。
#
#   質問の種類                     → grounding 先
#   ------------------------------ + ------------------------------
#   社内規程・手順書               → VertexAiSearchTool（非構造化・社内）
#   時事・公開情報                 → google_search（非構造化・公開）
#   口座・注文・取引のデータ       → sql_query_tool（構造化）
#
# 最後の 2 行（記憶で答えない／見つからなければそう言う）が
# ハルシネーション対策として最も効く部分。
#
# この retrieval_router は Cloud 環境が無くても動く（下の 2 つの tool は
# ローカル実装）。adk web で試すときは agent.py の root_agent を
# retrieval_router に差し替える。
# =====================================================================

import os

from google.adk import Agent

from .structured_data import query_orders

# .env の GEMINI_MODEL で差し替え可能
MODEL = os.environ.get("GEMINI_MODEL", "gemini-flash-latest")

# ---------------------------------------------------------------------
# 汎用の instruction の型（3 種類の grounding 先を持つ agent 用）
# ---------------------------------------------------------------------
ROUTING_INSTRUCTION = """
For internal policies or documentation: use VertexAiSearchTool.
For current events or public information: use google_search.
For account, order, or transaction data: use sql_query_tool.
Do not answer a factual question from memory if a tool can supply the answer.
If no tool returns a result, say so rather than estimating.
"""

# ---------------------------------------------------------------------
# 構造化（SQL）と非構造化（文書検索）の 2 つを持つ router
# ---------------------------------------------------------------------
sql_query_tool = query_orders  # structured_data.py のカスタム function tool

_POLICIES = {
    "return-policy.md": "Delivered orders can be returned within 30 days. Opened software cannot be returned.",
    "shipping-rules.md": "Standard shipping takes 3-5 business days. Orders over USD 50 ship free.",
    "warranty.md": "Electronics carry a 1-year limited warranty from the delivery date.",
}


def search_documents_tool(query: str) -> dict:
    """Searches internal policy documents and returns matching passages.

    Args:
        query: Keywords describing the policy question, e.g. "return window".

    Returns:
        dict: 'status' is "success" or "not_found".
            On success: 'results' is a list of dicts with 'document' (str,
            the file name to cite) and 'passage' (str).
            "not_found" means no policy covers the question -- say so.
    """
    # 本番ではここが Agent Search（VertexAiSearchTool）になる。
    # デモ用に単純なキーワード一致で代用している。
    words = [w.lower() for w in query.split() if len(w) > 2]
    hits = [
        {"document": name, "passage": text}
        for name, text in _POLICIES.items()
        if any(w in (name + " " + text).lower() for w in words)
    ]
    if not hits:
        return {"status": "not_found", "message": "No matching policy document."}
    return {"status": "success", "results": hits}


retrieval_router = Agent(
    name="retrieval_router",
    model=MODEL,
    instruction="""
    For structured records (orders, accounts, inventory): use sql_query_tool.
    For policies or procedures: use search_documents_tool.
    For questions needing both: call both and synthesize.
    Do not answer from memory. If neither returns a result, say so.
    """,
    tools=[sql_query_tool, search_documents_tool],
)
