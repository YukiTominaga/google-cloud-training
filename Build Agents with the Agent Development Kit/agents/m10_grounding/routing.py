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
社内ポリシーやドキュメントには VertexAiSearchTool を使ってください。
時事情報や公開情報には google_search を使ってください。
アカウント、注文、取引のデータには sql_query_tool を使ってください。
tool で答えが得られる事実に関する質問には、記憶で答えないでください。
どの tool も結果を返さない場合は、推測せずにその旨を伝えてください。
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
    """社内のポリシー文書を検索し、該当する一節を返す。

    Args:
        query: ポリシーに関する質問を表すキーワード。例: "return window"。

    Returns:
        dict: 'status' は "success" または "not_found"。
            成功時: 'results' は 'document'（str、引用するファイル名）と
            'passage'（str）を持つ dict のリスト。
            "not_found" はその質問に該当するポリシーがないことを意味する。その旨を伝えること。
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
    構造化されたレコード（注文、アカウント、在庫）には sql_query_tool を使ってください。
    ポリシーや手続きには search_documents_tool を使ってください。
    両方が必要な質問では、両方を呼び出して内容を統合してください。
    記憶で答えないでください。どちらも結果を返さない場合は、その旨を伝えてください。
    """,
    tools=[sql_query_tool, search_documents_tool],
)
