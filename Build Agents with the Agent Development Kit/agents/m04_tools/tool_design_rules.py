# =====================================================================
# M4 Code 2〜6. tool 設計の 5 ルール ― ❌ / ✅ の対比集
# ---------------------------------------------------------------------
# スライドで 1 ルールずつ見せるための対比コードです。
# adk web には読み込まれません（agent.py からも import していません）。
# =====================================================================

from google.adk.tools import ToolContext


# =====================================================================
# Code 2. ルール 1 ― 関数名がそのまま tool の名前になる
# ---------------------------------------------------------------------
# モデルは「名前」を見て、どの tool を使うかの当たりを付ける。
# 汎用的すぎる名前は、何をする tool なのか伝わらない。
#
#   ❌ get_data   → ✅ lookup_account
#   ❌ process    → ✅ initiate_return
#   ❌ helper2    → ✅ get_delivery_estimate
# =====================================================================
def get_data(x: str) -> dict:  # ❌ 何の data を取るのか分からない
    """Gets data."""
    return {}


def get_delivery_estimate(order_id: str) -> dict:  # ✅ 動詞＋目的語で具体的
    """Returns the estimated delivery date for an order.

    Args:
        order_id: The order to estimate, in the form "O-5001".

    Returns:
        dict: 'status' and, on success, 'eta' (str, YYYY-MM-DD).
    """
    return {"status": "success", "eta": "2026-09-30"}


# =====================================================================
# Code 3. ルール 2 ― docstring が最も重要
# ---------------------------------------------------------------------
# docstring に必ず書く 3 点
#   1. tool の目的
#   2. 各パラメータが何を期待しているのか
#   3. 戻り値をどう解釈するのか（エラーケースを含む）  ← 一番抜けやすい
# =====================================================================
def initiate_return_weak(order_id: str) -> dict:  # ❌ 目的しか書いていない
    """Starts a return."""
    return {"status": "success", "rma_id": "RMA-0001"}


def initiate_return(order_id: str) -> dict:  # ✅ 3 点が揃っている
    """Starts a return for a delivered order and issues an RMA ID.

    Args:
        order_id: The order to return, in the form "O-5001".

    Returns:
        dict: 'status' is "success" or "error".
            On success: 'rma_id' (str) is the return authorization ID.
            On error: 'message' (str). An error means the order is not
            eligible for return -- do not promise a refund.
    """
    return {"status": "success", "rma_id": "RMA-0001"}


# =====================================================================
# Code 4. ルール 3 ― すべてに型ヒントを付ける
# ---------------------------------------------------------------------
# 型ヒントが無いと、schema の properties に "type" が出ない。
#   {"properties": {"id": {"title": "Id"}}}   ← "type" が無い
# 実際の schema は show_schema.py で確認できる。
# =====================================================================
def bad(id) -> dict:  # ❌ 型ヒントなし
    ...


def good(account_id: str) -> dict:  # ✅ 引数にも戻り値にも型ヒント
    """Returns a placeholder result.

    Args:
        account_id: The unique identifier for the customer account.

    Returns:
        dict: 'status'.
    """
    return {"status": "success"}


# =====================================================================
# Code 5. ルール 4 ― 複雑な関数には ToolContext を使う
# ---------------------------------------------------------------------
# 引数名 tool_context に型 ToolContext を付けると、ADK が自動で注入する。
# この引数は schema に「出てこない」＝ モデルからは見えない・渡せない。
# session state・artifact・memory へのアクセスはすべてここ経由（M5）。
# =====================================================================
def fetch_account(account_id: str, tool_context: ToolContext) -> dict:
    """Returns account data for the authenticated user.

    Args:
        account_id: The account to fetch.

    Returns:
        dict: 'status' and, on success, 'balance'.
    """
    ...  # 中身は M5 で実装する


# =====================================================================
# Code 6. ルール 5 ― tool 間の依存関係を instruction に明示する
# ---------------------------------------------------------------------
# 「A が成功してから B を呼ぶ」という順序は、モデルには自明ではない。
# instruction に書かないと、いきなり B を呼んだり、A の失敗を無視したりする。
# =====================================================================
DEPENDENCY_INSTRUCTION = """
First use `lookup_account` with the customer's account ID.
If the account is valid, use the returned account ID to call `fetch_transactions`.
Never call `fetch_transactions` before `lookup_account` has succeeded.
"""
