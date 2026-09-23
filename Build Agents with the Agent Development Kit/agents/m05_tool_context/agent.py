# =====================================================================
# M5 ― Tool Context: State, Flow, and Artifacts
# Code 5. 通し題材 ― billing_agent に認可を入れる
# ---------------------------------------------------------------------
# ■ 前回（M4）から引き継ぐもの
#   5 ルールで設計した lookup_account / list_invoices。
# ■ 今回足すもの
#   ToolContext 経由で次の 3 つを tool に持たせる。
#     1. State access … 「誰が聞いているか」を state から読み、認可する
#     2. Flow control … tool が次の一手（agent の切り替え等）を指示する
#     3. Artifacts    … PDF のような大きなデータを会話の外に置く
#
#   Code 1〜3 の単独の例は tool_context_examples.py、
#   Runner から state を渡して実行する例は run_with_session.py にあります。
#     cd agents && python -m m05_tool_context.run_with_session
# =====================================================================

import os
from typing import Optional

from google.adk import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.tools import ToolContext
from google.genai import types

# .env の GEMINI_MODEL で差し替え可能
MODEL = os.environ.get("GEMINI_MODEL", "gemini-flash-latest")

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


# =====================================================================
# Code 2 / Code 5. State access ― 認可を tool に置く
# ---------------------------------------------------------------------
# ポイント：account_id（聞かれている口座）はモデルから渡されるが、
#           session_user_id（ログイン中の顧客）はアプリが state に入れる。
#           LLM が書き換えられない値と突き合わせるので、
#           「A-1002 の残高を教えて」と言われても他人の口座は見せない。
#           → 認可は instruction（お願い）ではなく tool（コード）に置く。
# =====================================================================
def lookup_account(account_id: str, tool_context: ToolContext) -> dict:
    """Returns the current balance and status for a customer account.

    Args:
        account_id: The unique identifier for the customer account,
            in the form "A-1001".

    Returns:
        dict: 'status' is "success", "error", or "denied".
            On success: 'balance' (float, USD) and 'account_status' (str).
            "denied" means the signed-in customer does not own that account --
            apologize and do not reveal any figures.
    """
    # tool_context.state は dict のように読み書きできる（session state）
    authorized_id = tool_context.state.get("session_user_id")
    if authorized_id is None:
        return {"status": "error", "message": "No signed-in customer."}
    if account_id != authorized_id:
        # 「見つからない(error)」と「見せられない(denied)」を区別して返す
        return {"status": "denied", "message": "Access denied."}

    account = _ACCOUNTS.get(account_id)
    if account is None:
        return {"status": "error", "message": f"Account {account_id} not found."}

    # 後続の tool / agent が使えるように、確認済みのアカウントを記録しておく。
    # tool_context.state への書き込みは、ADK がイベントとして記録・永続化する
    # （＝ managed context。M6 で詳しく扱う）。
    tool_context.state["verified_account_id"] = account_id
    return {"status": "success", **account}


def list_invoices(tool_context: ToolContext, limit: int = 3) -> dict:
    """Lists the most recent invoices for the verified account.

    Only call this after `lookup_account` has returned status "success".

    Args:
        limit: How many invoices to return, most recent first. Defaults to 3.

    Returns:
        dict: 'status' is "success" or "error".
            On success: 'invoices' is a list of dicts with
            'id' (str), 'amount' (float, USD) and 'issued_on' (str, YYYY-MM-DD).
            "error" means no account has been verified yet -- call
            `lookup_account` first.
    """
    # account_id を引数で受け取らず、認可済みの値を state から読む。
    # こうするとモデルが別の ID を渡して回り込む余地がそもそも無くなる。
    account_id = tool_context.state.get("verified_account_id")
    if account_id is None:
        return {"status": "error", "message": "No verified account. Call lookup_account first."}
    invoices = sorted(_INVOICES.get(account_id, []), key=lambda i: i["issued_on"], reverse=True)
    return {"status": "success", "invoices": invoices[:limit]}


# =====================================================================
# Code 4. Artifacts ― 大容量データを会話から逃がす
# ---------------------------------------------------------------------
# 数 MB の PDF をそのまま戻り値に入れると、会話履歴（＝毎回モデルに
# 送られるコンテキスト）が膨れ上がる。
# save_artifact で会話の外に保存し、戻り値には「ファイル名とバージョン」
# だけを返す。adk web では画面上に artifact として表示・ダウンロードできる。
#
# ※ ADK 2.9.2 では save_artifact / load_artifact / list_artifacts /
#    search_memory はすべて async。tool 自体も async def で書き、await する。
#    await を忘れるとコルーチンオブジェクトがモデルに渡ってしまう。
# =====================================================================
def _render_invoices_pdf(account_id: str) -> bytes:
    """請求書一覧を最小構成の PDF バイト列にする（デモ用の簡易実装）。

    本番では reportlab 等で作る想像で OK。ここでは「大きなバイナリが
    手元にある」状況を再現できれば十分なので、手書きの PDF を返す。
    """
    lines = [f"Invoices for {account_id}"] + [
        f"{inv['id']}  {inv['issued_on']}  USD {inv['amount']:.2f}"
        for inv in _INVOICES.get(account_id, [])
    ]
    # PDF のテキスト描画命令（1 行ずつ下にずらして描く）
    text_ops = "".join(f"({line}) Tj 0 -20 Td " for line in lines)
    stream = f"BT /F1 14 Tf 72 720 Td {text_ops}ET"
    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        "/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    body, offsets = "%PDF-1.4\n", []
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(body))
        body += f"{i} 0 obj\n{obj}\nendobj\n"
    xref_pos = len(body)
    body += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n"
    body += "".join(f"{off:010d} 00000 n \n" for off in offsets)
    body += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n"
    return body.encode("latin-1")


async def export_invoices_pdf(tool_context: ToolContext) -> dict:
    """Renders the verified account's invoices as a PDF and stores it for download.

    Only call this after `lookup_account` has returned status "success".

    Returns:
        dict: 'status', and on success 'filename' and 'version' of the
              stored artifact. The PDF itself is not returned inline.
    """
    account_id = tool_context.state.get("verified_account_id")
    if account_id is None:
        return {"status": "error", "message": "No verified account. Call lookup_account first."}

    pdf_bytes = _render_invoices_pdf(account_id)  # 本番では数 MB になり得る
    # バイト列を「MIME タイプ付きの Part」に包んで保存する
    part = types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf")
    filename = f"{account_id}_invoices.pdf"
    # 同じファイル名で保存し直すとバージョンが 1 つ上がる（上書きではない）
    version = await tool_context.save_artifact(filename, part)
    return {"status": "success", "filename": filename, "version": version}


async def read_back(filename: str, tool_context: ToolContext) -> dict:
    """Loads a previously stored artifact.

    Args:
        filename: The artifact name returned by a previous export.

    Returns:
        dict: 'status' and 'size_bytes' of the artifact.
    """
    part = await tool_context.load_artifact(filename)  # 最新バージョンを読む
    if part is None:
        return {"status": "error", "message": f"No artifact named {filename}."}
    # 中身は会話に戻さず、サイズだけ返す（会話を軽く保つ）
    return {"status": "success", "size_bytes": len(part.inline_data.data)}


# =====================================================================
# adk web でデモするための補助（講義用）
# ---------------------------------------------------------------------
# 本来 session_user_id は「ログイン処理を終えたアプリ」が
# セッション作成時に入れる値です（run_with_session.py を参照）。
# adk web にはログインが無いので、未設定のときだけ A-1001 として
# ログインしている扱いにします。callback 自体は M6 で詳しく扱います。
# =====================================================================
DEMO_SIGNED_IN_ACCOUNT = "A-1001"


def _demo_sign_in(callback_context: CallbackContext) -> Optional[types.Content]:
    """agent 実行前に呼ばれ、デモ用のログイン状態を state に用意する。"""
    if callback_context.state.get("session_user_id") is None:
        callback_context.state["session_user_id"] = DEMO_SIGNED_IN_ACCOUNT
    return None  # None を返す = 通常どおり agent を実行する


root_agent = Agent(
    name="billing_agent",
    model=MODEL,
    description="Answers billing and payment questions for the signed-in customer.",
    instruction="""You are a billing specialist for an online retailer.
Scope: account balances, invoices, and invoice PDFs for the signed-in customer.

Tool order:
1. Always call `lookup_account` first with the account ID the customer asks about.
2. Only after it returns status "success", you may call `list_invoices`
   or `export_invoices_pdf`.

Rules:
- If a tool returns status "denied", apologize and say you can only share
  information about the customer's own account. Do not reveal any figures.
- If a tool returns status "error", say so. Do not estimate.
- After exporting a PDF, tell the customer the file name. Never paste the PDF.
""",
    tools=[lookup_account, list_invoices, export_invoices_pdf, read_back],
    before_agent_callback=_demo_sign_in,
)
