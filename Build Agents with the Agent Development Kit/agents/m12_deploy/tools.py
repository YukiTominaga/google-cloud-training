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
    """Returns the current balance and status for a customer account.

    Call this before answering any question about a balance or payment.

    Args:
        account_id: The unique identifier for the customer account,
            in the form "A-1001".

    Returns:
        dict: 'status' is "success" or "error".
            On success: 'balance' (float, USD) and 'account_status' (str).
            An error means the account does not exist -- do not guess.
    """
    account = _ACCOUNTS.get(account_id)
    if account is None:
        return {"status": "error", "message": f"Account {account_id} not found."}
    return {"status": "success", "account_id": account_id, **account}


def list_invoices(account_id: str, limit: int = 3) -> dict:
    """Lists the most recent invoices for a customer account.

    Only call this after `lookup_account` has returned status "success".

    Args:
        account_id: The unique identifier for the customer account.
        limit: How many invoices to return, most recent first. Defaults to 3.

    Returns:
        dict: 'status' is "success" or "error".
            On success: 'invoices' is a list of dicts with 'id' (str),
            'amount' (float, USD) and 'issued_on' (str, YYYY-MM-DD).
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
    """Returns the current shipping status of an order.

    Args:
        order_id: The order to track, in the form "O-5001".

    Returns:
        dict: 'status' is "success" or "error".
            On success: 'order_status' (str, one of "processing", "shipped",
            "delivered") and 'carrier' (str or null if not shipped yet).
            An error means the order does not exist.
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
    """Returns the estimated delivery date for an order that is not yet delivered.

    Args:
        order_id: The order to estimate, in the form "O-5001".

    Returns:
        dict: 'status' is "success" or "error".
            On success: 'eta' (str, YYYY-MM-DD).
            An error means the order does not exist or was already delivered.
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
    """Returns the details of an order needed to decide on a return.

    Args:
        order_id: The order to look up, in the form "O-5001".

    Returns:
        dict: 'status' is "success" or "error".
            On success: 'order_status' (str), 'placed_on' (str, YYYY-MM-DD),
            'delivered_on' (str or null) and 'total' (float, USD).
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
    """Checks whether an order is eligible for return under the current policy.

    Call this after `lookup_order` and before `initiate_return`.

    Args:
        order_id: The order to check, in the form "O-5001".

    Returns:
        dict: 'status' is "success" or "error".
            On success: 'eligible' (bool) and 'reason' (str).
            If 'eligible' is false, do not call `initiate_return`.
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
    """Starts a return for an eligible order and issues an RMA ID.

    Only call this after `check_return_policy` returned 'eligible' true.

    Args:
        order_id: The order to return, in the form "O-5001".
        reason: The customer's reason for the return, in their own words.

    Returns:
        dict: 'status' is "success" or "error".
            On success: 'rma_id' (str) is the return authorization ID.
            An error means the return could not be started -- do not
            promise a refund.
    """
    if order_id not in _ORDERS:
        return {"status": "error", "message": f"Order {order_id} not found."}
    # 実際にはここで返品システムに登録する（外部への副作用がある処理）
    return {"status": "success", "rma_id": f"RMA-{order_id[2:]}", "reason": reason}
