# =====================================================================
# M2 ― Configuring a Simple Agent
# ---------------------------------------------------------------------
# ■ 前回（M1）から引き継ぐもの
#   20 行の billing_agent。
# ■ 今回足すもの
#   Code 1. 必須 3 要素（name / model / instruction）だけの agent
#   Code 2. 弱い instruction と強い instruction の比較（このモジュールの本体）
#   Code 3. 任意パラメータ（description / tools / output_key /
#           generate_content_config）を詰めた agent  ← root_agent
#   Code 4. output_schema で構造化 JSON を返させる agent
#
# ■ adk web で動くのは root_agent（Code 3 の完成形）です。
#   Code 1 / Code 4 の agent は比較用に同じファイルに置いています。
#   試したいときは末尾の root_agent の代入先を差し替えてください。
#
# ■ 試すプロンプト（adk web / adk run で入力）
#   1. 「A-1001 の残高を教えて」
#      → lookup_account が呼ばれ、残高 128.50 と状態 active が返る。
#        最終応答が output_key で state["billing_response"] に保存される（State タブで確認）
#   2. 「A-1001 の直近の請求書を見せて」
#      → list_invoices が呼ばれ、INV-9001 / INV-9002（各 64.25 USD）が返る
#   3. 「注文した商品の配送状況は？」
#      → 対応範囲外。tool を呼ばずに、担当者に引き継ぐと答える
#        （instruction を WEAK_INSTRUCTION に変えると差が分かる）
#   4. 「A-1002 の残高は？」
#      → M2 の lookup_account には A-1001 しか無いので status "error"。
#        推測せずに、アカウントが見つからなかったと伝える
#   ※ root_agent を structured_billing_agent に差し替えて 1 を送ると、
#     応答が BillingResult（account_id / balance / summary）の JSON になる
# =====================================================================

import os

from google.adk import Agent
from google.genai import types  # generate_content_config 用（Gemini SDK の型）
from pydantic import BaseModel, Field

# .env の GEMINI_MODEL で差し替え可能
MODEL = os.environ.get("GEMINI_MODEL", "gemini-flash-latest")


# =====================================================================
# Code 1. 3 要素だけの agent
# ---------------------------------------------------------------------
# 必須なのは name / model / instruction の 3 つだけ。
# tool が無いので「残高を教えて」と聞いても答えようがない
# （＝ tool の必要性を体感させるための最小形）。
# =====================================================================
minimal_billing_agent = Agent(
    name="minimal_billing_agent",
    model=MODEL,
    instruction=(
        "あなたは請求担当のスペシャリストです。アカウント残高、支払い履歴、"
        "請求書に関する質問に答えてください。"
    ),
)


# =====================================================================
# Code 2. instruction ― 弱い版と強い版
# ---------------------------------------------------------------------
# 弱い版：何を扱い、何を扱わないのかが不明。
#         配送や返品の質問にも「それっぽく」答えてしまう。
# 強い版：次の 3 点が明示されている。
#   1. 対応範囲 … 扱う範囲と「扱わない」範囲
#   2. ツール   … どの tool を何のために使うか
#   3. ルール   … 失敗時の振る舞い（推測で答えない）
# =====================================================================
WEAK_INSTRUCTION = "あなたは親切なカスタマーサービスのアシスタントです。"

STRONG_INSTRUCTION = """あなたはオンライン小売店の請求担当スペシャリストです。

対応範囲:
- アカウント残高、支払い履歴、請求書に関する質問に答えてください。
- 配送、返品、在庫に関する質問には答えないでください（厳守）。
  それらの質問には、適切な担当者に引き継ぐと伝えてください。

ツール:
- アカウント ID の現在の残高を取得するには `lookup_account` を使ってください。
- アカウント ID の直近の請求書を一覧するには `list_invoices` を使ってください。

ルール:
- `lookup_account` から得たもの以外の残高は絶対に伝えないでください。
- tool が {"status": "error"} を返した場合は、アカウントが見つからなかったと
  顧客に伝えてください。推測や概算はしないでください。
"""


# =====================================================================
# Code 3 で使う tool（M1 と同じ作法：引数は文字列、戻り値は status 付き dict）
# =====================================================================
def lookup_account(account_id: str) -> dict:
    """指定したアカウントの現在の残高とステータスを返す。

    Args:
        account_id: 顧客アカウントの一意な ID。

    Returns:
        dict: 'status'（"success" または "error"）。成功時は
              'balance'（float）と 'account_status'（str）も含む。
    """
    accounts = {"A-1001": {"balance": 128.50, "account_status": "active"}}
    if account_id not in accounts:
        return {"status": "error", "message": f"Account {account_id} not found."}
    return {"status": "success", **accounts[account_id]}


def list_invoices(account_id: str) -> dict:
    """指定したアカウントの直近の請求書を一覧で返す。

    Args:
        account_id: 顧客アカウントの一意な ID。

    Returns:
        dict: 'status'（"success" または "error"）。成功時は
              'invoices'（'id'・'amount'・'issued_on' を持つ dict のリスト）も含む。
    """
    # M2 では固定値を返すだけ（アカウントの存在チェックは M4 で入れる）
    return {
        "status": "success",
        "invoices": [
            {"id": "INV-9001", "amount": 64.25, "issued_on": "2026-08-01"},
            {"id": "INV-9002", "amount": 64.25, "issued_on": "2026-09-01"},
        ],
    }


# =====================================================================
# Code 3. 任意パラメータ入りの agent（このファイルの root_agent）
# =====================================================================
billing_agent = Agent(
    name="billing_agent",
    model=MODEL,
    # description：外から見た看板（M7 / M9 で親が委譲先を選ぶ材料）
    description="Answers billing and payment questions.",
    # instruction：Code 2 の「強い版」を使う
    instruction=STRONG_INSTRUCTION,
    # tools：関数を並べるだけ。順番に意味はない
    tools=[lookup_account, list_invoices],
    # output_key：agent の最終応答テキストを session state の
    #             state["billing_response"] に自動保存する。
    #             M6（state）・M7（複数 agent の受け渡し）で効いてくる。
    output_key="billing_response",
    # generate_content_config：モデルの生成パラメータ。
    #   temperature を下げる = 答えのブレを小さくする。
    #   数字を扱う billing では低め（0.2 程度）が無難。
    generate_content_config=types.GenerateContentConfig(temperature=0.2),
)


# =====================================================================
# Code 4. output_schema ― 構造化 JSON を返させる
# ---------------------------------------------------------------------
# Pydantic モデルを渡すと、応答がそのスキーマに沿った JSON になる。
# Field(description=...) はモデルへの「各項目の意味の説明」として使われる。
# ※ ADK 2.9.2 では tools と output_schema を同時に指定できる
#   （古いバージョンでは併用不可だった点に注意）。
# =====================================================================
class BillingResult(BaseModel):
    account_id: str = Field(description="The account that was looked up.")
    balance: float = Field(description="Current balance in USD.")
    summary: str = Field(description="One-sentence summary for the customer.")


structured_billing_agent = Agent(
    name="structured_billing_agent",
    model=MODEL,
    description="Answers billing and payment questions.",
    instruction="アカウントを照会し、BillingResult を返してください。",
    tools=[lookup_account],
    output_schema=BillingResult,  # ← 応答の「形」を固定する
)


# ---------------------------------------------------------------------
# adk web / adk run が読み込むのはこの変数だけ。
# 比較デモでは右辺を minimal_billing_agent / structured_billing_agent に
# 差し替えて再読み込みしてください。
# 弱い instruction を試すときは billing_agent の instruction を
# WEAK_INSTRUCTION に変え、「配送状況は？」と聞いてみると差が分かります。
# ---------------------------------------------------------------------
root_agent = billing_agent
