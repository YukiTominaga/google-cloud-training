# =====================================================================
# M10 Code 3. 構造化データ ― カスタム function tool
# ---------------------------------------------------------------------
# 注文・口座・在庫のような「表」のデータは、検索ではなく SQL で引く。
# 組み込み tool に頼らず、M4 / M5 の作法で自分で function tool を書く。
#
# ■ 見せたいポイント
#   1. 認可は tool の中で（M5 の session_user_id と同じ）
#   2. SQL はパラメータ化する（@account_id）。モデルが作った文字列を
#      SQL に連結しない ＝ SQL インジェクションを構造的に防ぐ
#   3. DB エラーは例外で落とさず、status="error" の dict で返す
#
# 本サンプルでは BigQuery の代わりに、標準ライブラリの sqlite3 の
# インメモリ DB を使うので、Cloud 環境なしでそのまま動きます。
# （本番の BigQuery なら BigQueryToolset を使う手もある）
# =====================================================================

import re
import sqlite3

from google.adk.tools import ToolContext

# DB ドライバの例外クラス。BigQuery なら google.api_core.exceptions.GoogleAPIError 等
DatabaseError = sqlite3.DatabaseError

# ---------------------------------------------------------------------
# ダミーの「注文ウェアハウス」
# ---------------------------------------------------------------------
_conn = sqlite3.connect(":memory:", check_same_thread=False)
_conn.row_factory = sqlite3.Row
_conn.executescript(
    """
    CREATE TABLE orders (order_id TEXT, account_id TEXT, placed_on TEXT, total REAL);
    INSERT INTO orders VALUES
      ('O-5001', 'A-1001', '2026-09-15', 64.25),
      ('O-5002', 'A-1001', '2026-08-20', 19.80),
      ('O-5003', 'A-1002', '2026-09-21', 42.00);
    """
)


def run_sql(sql: str, **params) -> list[dict]:
    """BigQuery 風の @name パラメータ付き SQL を実行し、行を dict のリストで返す。

    sqlite3 は :name 形式なので、@name を :name に置き換えてから実行する。
    値は必ずパラメータとして渡し、SQL 文字列には埋め込まない。
    """
    sqlite_sql = re.sub(r"@(\w+)", r":\1", sql)
    rows = _conn.execute(sqlite_sql, params).fetchall()
    return [dict(row) for row in rows]


def query_orders(account_id: str, limit: int = 10, *, tool_context: ToolContext) -> dict:
    """Returns recent orders for a customer account from the orders warehouse.

    Args:
        account_id: The unique identifier for the customer account.
        limit: How many orders to return, most recent first. Defaults to 10.

    Returns:
        dict: 'status' is "success", "denied", or "error".
            On success: 'orders' is a list of dicts with 'order_id' (str),
            'placed_on' (str, YYYY-MM-DD), and 'total' (float, USD).
            "denied" means the signed-in customer does not own that account.
    """
    # ① 認可：LLM が渡した account_id を、アプリが入れた値と突き合わせる
    if tool_context.state.get("session_user_id") != account_id:
        return {"status": "denied", "message": "Access denied."}
    # ② パラメータ化クエリ
    try:
        rows = run_sql(
            "SELECT order_id, placed_on, total FROM orders "
            "WHERE account_id = @account_id ORDER BY placed_on DESC LIMIT @limit",
            account_id=account_id,
            limit=limit,
        )
    # ③ 例外はその DB ドライバの例外だけを捕まえる（広い except Exception は書かない）
    except DatabaseError as exc:
        return {"status": "error", "message": f"Query failed: {exc}"}
    return {"status": "success", "orders": rows}
