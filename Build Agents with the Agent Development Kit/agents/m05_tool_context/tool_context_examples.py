# =====================================================================
# M5 Code 1〜3. ToolContext の単独の例
# ---------------------------------------------------------------------
# スライドで 1 つずつ見せるための部品です（adk web には読み込まれません）。
# 通し題材に組み込んだ完成形は agent.py を参照してください。
# =====================================================================

from google.adk.tools import ToolContext

from .agent import lookup_account as _lookup_account_with_auth


# =====================================================================
# Code 1. ToolContext の受け取り方
# ---------------------------------------------------------------------
# ・最後の引数に「tool_context: ToolContext」と書くだけで ADK が注入する
# ・この引数は schema に出ない ＝ モデルからは見えない
# ・ToolContext から触れる主なもの
#     tool_context.state            … session state の読み書き
#     await tool_context.search_memory(...)  … 長期記憶の検索（M11）
#     await tool_context.list_artifacts()    … 保存済みファイルの一覧
#     tool_context.actions          … 次の一手の指示（Code 3）
# =====================================================================
async def tool_function(user_query: str, tool_context: ToolContext) -> dict:
    """Generic tool function.

    Args:
        user_query: The user's query.

    Returns:
        dict: the result of the lookup.
    """
    # session state の読み書き（同期。dict と同じ感覚で扱える）
    tool_context.state["user_query"] = user_query
    user_preferences = tool_context.state.get("user_preferences")

    # 長期記憶の検索（async → await が必要）
    relevant_docs = await tool_context.search_memory(f"info related to {user_query}")

    # 保存済み artifact の一覧（async → await が必要）
    available_files = await tool_context.list_artifacts()

    return {
        "status": "success",
        "preferences": user_preferences,
        "memory_hits": len(relevant_docs.memories),
        "files": available_files,
    }


# =====================================================================
# Code 2. State access ― 認可を tool に置く（最小形）
# ---------------------------------------------------------------------
# agent.py の lookup_account は、この形を通し題材に組み込んだもの。
# =====================================================================
def fetch_account(account_id: str, tool_context: ToolContext) -> dict:
    """Returns account data for the authenticated user.

    Args:
        account_id: The account the customer is asking about.

    Returns:
        dict: 'status' and, on success, 'balance'. 'status' is "error"
              when the caller is not authorized for that account.
    """
    # session_user_id はセッション開始時にアプリが設定するもので、
    # LLM から渡されるものではない
    authorized_id = tool_context.state.get("session_user_id")
    if account_id != authorized_id:
        return {"status": "error", "message": "Access denied."}
    return _lookup_account_with_auth(account_id, tool_context)


# =====================================================================
# Code 3. Flow control ― tool が次の一手を指示する
# ---------------------------------------------------------------------
# tool_context.actions に値を入れると、tool の実行後に ADK がそれに従う。
#   actions.transfer_to_agent = "xxx" … 会話を別の agent に引き継ぐ
#   actions.escalate = True           … 親 agent に制御を返す（ループ脱出など）
#   actions.skip_summarization = True … tool の結果をモデルに要約させない
#
# ※ transfer_to_agent の行き先は、同じ agent ツリーに実在する name であること。
#   billing / shipping / returns の 3 体が揃うのは M7 以降。
# =====================================================================
def route_to_specialist(category: str, tool_context: ToolContext) -> dict:
    """Hands the conversation to the specialist for the given category.

    Args:
        category: One of "billing", "shipping", or "returns".

    Returns:
        dict: 'status' and the agent the conversation was handed to.
    """
    targets = {
        "billing": "billing_agent",
        "shipping": "shipping_agent",
        "returns": "returns_agent",
    }
    target = targets.get(category)
    if target is None:
        return {"status": "error", "message": f"Unknown category: {category}"}
    # 「次はこの agent に話させて」という指示をフレームワークに渡す
    tool_context.actions.transfer_to_agent = target
    return {"status": "success", "transferred_to": target}
