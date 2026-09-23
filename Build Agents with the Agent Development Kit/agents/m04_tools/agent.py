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
    """顧客アカウントの現在の残高とステータスを返す。

    残高・支払い・アカウントが有効かどうかに関する質問に答える前に、
    必ずこれを呼び出すこと。

    Args:
        account_id: 顧客アカウントの一意な ID。"A-1001" の形式。

    Returns:
        dict: 'status' は "success" または "error"。
            成功時: 'balance'（float、USD）と
            'account_status'（str、"active" または "suspended"）。
            エラー時: 'message'（str）に照会に失敗した理由が入る。
            エラーはアカウントが存在しないことを意味する。残高を推測しないこと。
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
#   instruction（下の「tool の呼び出し順」）にも書く ＝ ルール 5。
def list_invoices(account_id: str, limit: int = 3) -> dict:
    """顧客アカウントの直近の請求書を一覧で返す。

    同じ account_id に対して `lookup_account` が status "success" を
    返した後にだけ呼び出すこと。

    Args:
        account_id: 顧客アカウントの一意な ID。
        limit: 返す請求書の件数（新しい順）。既定値は 3。

    Returns:
        dict: 'status' は "success" または "error"。
            成功時: 'invoices' は dict のリストで、各要素は
            'id'（str）、'amount'（float、USD）、'issued_on'（str、YYYY-MM-DD）を持つ。
            空のリストは、そのアカウントに請求書の記録が無いことを意味する。
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
    instruction="""あなたはオンライン小売店の請求担当スペシャリストです。
対応範囲: アカウント残高、支払い履歴、請求書のみ。

tool の呼び出し順:
1. 必ず最初に、顧客のアカウント ID で `lookup_account` を呼び出してください。
2. それが status "success" を返した場合にだけ、同じアカウント ID で
   `list_invoices` を呼び出してかまいません。

ルール:
- tool から得たもの以外の残高や請求額は絶対に伝えないでください。
- tool が status "error" を返した場合は、アカウントが見つからなかったと
  顧客に伝えてください。概算はしないでください。
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
