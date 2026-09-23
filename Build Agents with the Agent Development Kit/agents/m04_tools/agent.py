# =====================================================================
# M4 ― Building Tools The Model Can Use
# Code 7. 通し題材 ― billing_agent の tool を揃える
# ---------------------------------------------------------------------
# ■ 前回（M3）から引き継ぐもの
#   adk web で動かしてトレースを読める billing_agent。
# ■ 今回足すもの
#   「モデルが正しく使える tool」を設計する 5 ルールを適用した
#   lookup_account / list_invoices。
#
#   ルール 1. 関数名がそのまま tool の名前になる   → 動詞＋目的語で具体的に
#   ルール 2. docstring が最も重要                 → 目的・引数・戻り値（エラー含む）
#   ルール 3. すべてに型ヒントを付ける             → 付けないと schema に type が出ない
#   ルール 4. 複雑な関数には ToolContext を使う    → M5 で本格的に
#   ルール 5. tool 間の依存関係を instruction に明示する
#
#   各ルールの ❌ / ✅ 対比は tool_design_rules.py、
#   「関数が schema になる」様子は show_schema.py で確認できます。
#     cd agents && python -m m04_tools.show_schema
# =====================================================================

import os

from google.adk import Agent

# .env の GEMINI_MODEL で差し替え可能
MODEL = os.environ.get("GEMINI_MODEL", "gemini-flash-latest")

# ---------------------------------------------------------------------
# ダミーデータ（先頭の _ は「モジュール内部用」の意味。tool ではない）
# ---------------------------------------------------------------------
_ACCOUNTS = {
    "A-1001": {"balance": 128.50, "account_status": "active"},
    "A-1002": {"balance": 0.00, "account_status": "suspended"},
}

_INVOICES = {
    "A-1001": [
        {"id": "INV-9001", "amount": 64.25, "issued_on": "2026-08-01"},
        {"id": "INV-9002", "amount": 64.25, "issued_on": "2026-09-01"},
    ],
    # A-1002 は請求書が 0 件（「空リスト」と「エラー」は意味が違う例）
    "A-1002": [],
}


# ---------------------------------------------------------------------
# tool 1：lookup_account
# ---------------------------------------------------------------------
# docstring の書き方のポイント（ルール 2）
#   1 行目       : tool の目的
#   2 段落目     : いつ呼ぶべきか（モデルが「呼ぶ判断」をする材料）
#   Args         : 各引数に何を期待するか（形式の例 "A-1001" まで書く）
#   Returns      : 戻り値の解釈。特にエラーのときにどう振る舞うべきか
def lookup_account(account_id: str) -> dict:
    """Returns the current balance and status for a customer account.

    Call this before answering any question about a balance, a payment,
    or whether an account is active.

    Args:
        account_id: The unique identifier for the customer account,
            in the form "A-1001".

    Returns:
        dict: 'status' is "success" or "error".
            On success: 'balance' (float, USD) and
            'account_status' (str, one of "active" or "suspended").
            On error: 'message' (str) explains why the lookup failed.
            An error means the account does not exist -- do not guess a balance.
    """
    account = _ACCOUNTS.get(account_id)
    if account is None:
        return {"status": "error", "message": f"Account {account_id} not found."}
    return {"status": "success", **account}


# ---------------------------------------------------------------------
# tool 2：list_invoices
# ---------------------------------------------------------------------
# ・limit: int = 3 のように既定値を付けると、schema 上は「任意引数」になる
#   （required に入らない）。
# ・「lookup_account の後に呼ぶ」という依存関係を docstring にも書き、
#   instruction（下の Tool order）にも書く ＝ ルール 5。
def list_invoices(account_id: str, limit: int = 3) -> dict:
    """Lists the most recent invoices for a customer account.

    Only call this after `lookup_account` has returned status "success"
    for the same account_id.

    Args:
        account_id: The unique identifier for the customer account.
        limit: How many invoices to return, most recent first. Defaults to 3.

    Returns:
        dict: 'status' is "success" or "error".
            On success: 'invoices' is a list of dicts, each with
            'id' (str), 'amount' (float, USD) and 'issued_on' (str, YYYY-MM-DD).
            An empty list means the account has no invoices on record.
    """
    invoices = _INVOICES.get(account_id)
    if invoices is None:
        return {"status": "error", "message": f"Account {account_id} not found."}
    # 新しい順に並べてから件数を絞る
    newest_first = sorted(invoices, key=lambda inv: inv["issued_on"], reverse=True)
    return {"status": "success", "invoices": newest_first[:limit]}


# ---------------------------------------------------------------------
# agent：instruction に「tool を呼ぶ順番」を明示する（ルール 5）
# ---------------------------------------------------------------------
root_agent = Agent(
    name="billing_agent",
    model=MODEL,
    description="Answers billing and payment questions.",
    instruction="""You are a billing specialist for an online retailer.
Scope: account balances, payment history, and invoices only.

Tool order:
1. Always call `lookup_account` first with the customer's account ID.
2. Only if it returns status "success", you may call `list_invoices`
   with the same account ID.

Rules:
- Never state a balance or an invoice amount that did not come from a tool.
- If a tool returns status "error", tell the customer the account could not
  be found. Do not estimate.
""",
    tools=[lookup_account, list_invoices],
)

# ---------------------------------------------------------------------
# Code 8. Python 関数以外の tool（参考：名前だけ紹介）
#   OpenAPI   … OpenAPIToolset：仕様のエンドポイントごとに tool を自動生成
#   MCP       … McpToolset：MCP サーバーの tool をそのまま取り込む（M10）
#   組み込み  … google_search / VertexAiSearchTool / BigQueryToolset（M10）
#   AgentTool … 別の agent を tool として呼ぶ（M9）
# ---------------------------------------------------------------------
