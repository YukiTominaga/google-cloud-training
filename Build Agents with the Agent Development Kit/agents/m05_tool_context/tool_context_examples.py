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
    """汎用的な tool 関数。

    Args:
        user_query: ユーザーの問い合わせ内容。

    Returns:
        dict: 照会の結果。
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
    """認証済みユーザーのアカウント情報を返す。

    Args:
        account_id: 顧客が尋ねているアカウント。

    Returns:
        dict: 'status'。成功時は 'balance' も含む。呼び出し元にその
              アカウントへのアクセス権が無い場合、'status' は "error" になる。
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
    """指定したカテゴリの担当者に会話を引き継ぐ。

    Args:
        category: "billing"、"shipping"、"returns" のいずれか。

    Returns:
        dict: 'status' と、会話の引き継ぎ先の agent。
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
