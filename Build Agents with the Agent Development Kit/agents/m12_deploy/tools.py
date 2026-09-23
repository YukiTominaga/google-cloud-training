# =====================================================================
# M12 でデプロイする agent の tool 一式（M7 の tools.py と同じ内容）
# ---------------------------------------------------------------------
# M4 の 5 ルール（具体的な関数名・3 点が揃った docstring・型ヒント・
# status 付き dict で返す）をそのまま適用しています。
# データはすべてダミーです。
# =====================================================================

# ---------------------------------------------------------------------
# ダミーデータ
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
    "A-1002": [],
}
_ORDERS = {
    "O-5001": {
        "account_id": "A-1001",
        "status": "shipped",
        "carrier": "Yamato",
        "placed_on": "2026-09-15",
        "delivered_on": None,
        "total": 64.25,
    },
    "O-5002": {
        "account_id": "A-1001",
        "status": "delivered",
        "carrier": "Sagawa",
        "placed_on": "2026-08-20",
        "delivered_on": "2026-08-23",
        "total": 19.80,
    },
    "O-5003": {
        "account_id": "A-1002",
        "status": "processing",
        "carrier": None,
        "placed_on": "2026-09-21",
        "delivered_on": None,
        "total": 42.00,
    },
}
_ETA = {"O-5001": "2026-09-25", "O-5003": "2026-09-28"}
_RETURN_WINDOW_DAYS = 30


# =====================================================================
# billing
# =====================================================================
def lookup_account(account_id: str) -> dict:
    """顧客アカウントの現在の残高とステータスを返す。

    残高や支払いに関する質問に答える前に、必ずこれを呼ぶこと。

    Args:
        account_id: 顧客アカウントの一意な ID。"A-1001" の形式。

    Returns:
        dict: 'status' は "success" または "error"。
            成功時: 'balance'（float, USD）と 'account_status'（str）。
            エラーはアカウントが存在しないことを意味する。推測で答えないこと。
    """
    account = _ACCOUNTS.get(account_id)
    if account is None:
        return {"status": "error", "message": f"Account {account_id} not found."}
    return {"status": "success", "account_id": account_id, **account}


def list_invoices(account_id: str, limit: int = 3) -> dict:
    """顧客アカウントの直近の請求書を一覧で返す。

    `lookup_account` が status "success" を返した後にのみ呼ぶこと。

    Args:
        account_id: 顧客アカウントの一意な ID。
        limit: 返す請求書の件数（新しい順）。既定値は 3。

    Returns:
        dict: 'status' は "success" または "error"。
            成功時: 'invoices' は 'id'（str）、'amount'（float, USD）、
            'issued_on'（str, YYYY-MM-DD）を持つ dict のリスト。
    """
    invoices = _INVOICES.get(account_id)
    if invoices is None:
        return {"status": "error", "message": f"Account {account_id} not found."}
    newest_first = sorted(invoices, key=lambda i: i["issued_on"], reverse=True)
    return {"status": "success", "invoices": newest_first[:limit]}


# =====================================================================
# shipping
# =====================================================================
def track_order(order_id: str) -> dict:
    """注文の現在の配送状況を返す。

    Args:
        order_id: 追跡する注文。"O-5001" の形式。

    Returns:
        dict: 'status' は "success" または "error"。
            成功時: 'order_status'（str。"processing"、"shipped"、
            "delivered" のいずれか）と 'carrier'（str。未発送なら null）。
            エラーは注文が存在しないことを意味する。
    """
    order = _ORDERS.get(order_id)
    if order is None:
        return {"status": "error", "message": f"Order {order_id} not found."}
    return {
        "status": "success",
        "order_id": order_id,
        "order_status": order["status"],
        "carrier": order["carrier"],
    }


def get_delivery_estimate(order_id: str) -> dict:
    """まだ配達されていない注文のお届け予定日を返す。

    Args:
        order_id: 予定日を調べる注文。"O-5001" の形式。

    Returns:
        dict: 'status' は "success" または "error"。
            成功時: 'eta'（str, YYYY-MM-DD）。
            エラーは注文が存在しないか、すでに配達済みであることを意味する。
    """
    if order_id not in _ORDERS:
        return {"status": "error", "message": f"Order {order_id} not found."}
    eta = _ETA.get(order_id)
    if eta is None:
        return {"status": "error", "message": f"Order {order_id} was already delivered."}
    return {"status": "success", "order_id": order_id, "eta": eta}


# =====================================================================
# returns
# =====================================================================
def lookup_order(order_id: str) -> dict:
    """返品の可否を判断するのに必要な注文の詳細を返す。

    Args:
        order_id: 調べる注文。"O-5001" の形式。

    Returns:
        dict: 'status' は "success" または "error"。
            成功時: 'order_status'（str）、'placed_on'（str, YYYY-MM-DD）、
            'delivered_on'（str または null）、'total'（float, USD）。
    """
    order = _ORDERS.get(order_id)
    if order is None:
        return {"status": "error", "message": f"Order {order_id} not found."}
    return {
        "status": "success",
        "order_id": order_id,
        "order_status": order["status"],
        "placed_on": order["placed_on"],
        "delivered_on": order["delivered_on"],
        "total": order["total"],
    }


def check_return_policy(order_id: str) -> dict:
    """注文が現在の返品ポリシーで返品可能かどうかを確認する。

    `lookup_order` の後、`initiate_return` の前に呼ぶこと。

    Args:
        order_id: 確認する注文。"O-5001" の形式。

    Returns:
        dict: 'status' は "success" または "error"。
            成功時: 'eligible'（bool）と 'reason'（str）。
            'eligible' が false なら `initiate_return` を呼ばないこと。
    """
    order = _ORDERS.get(order_id)
    if order is None:
        return {"status": "error", "message": f"Order {order_id} not found."}
    if order["status"] != "delivered":
        return {
            "status": "success",
            "eligible": False,
            "reason": "Only delivered orders can be returned.",
        }
    return {
        "status": "success",
        "eligible": True,
        "reason": f"Delivered orders can be returned within {_RETURN_WINDOW_DAYS} days.",
    }


def initiate_return(order_id: str, reason: str) -> dict:
    """返品可能な注文の返品手続きを開始し、RMA ID を発行する。

    `check_return_policy` が 'eligible' true を返した後にのみ呼ぶこと。

    Args:
        order_id: 返品する注文。"O-5001" の形式。
        reason: 顧客自身の言葉で書いた返品理由。

    Returns:
        dict: 'status' は "success" または "error"。
            成功時: 'rma_id'（str）は返品承認 ID。
            エラーは返品を開始できなかったことを意味する。返金を約束しないこと。
    """
    if order_id not in _ORDERS:
        return {"status": "error", "message": f"Order {order_id} not found."}
    # 実際にはここで返品システムに登録する（外部への副作用がある処理）
    return {"status": "success", "rma_id": f"RMA-{order_id[2:]}", "reason": reason}
