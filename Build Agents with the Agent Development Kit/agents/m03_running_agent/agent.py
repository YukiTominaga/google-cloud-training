# =====================================================================
# M3 ― Running Your First Agent
# ---------------------------------------------------------------------
# ■ 前回（M2）から引き継ぐもの
#   name / model / instruction / tools を詰めた billing_agent。
# ■ 今回のテーマ
#   コードを増やすのではなく「動かし方」と「トレースの読み方」を覚える。
#   コマンド一覧は同じフォルダの run_commands.sh にまとめています。
#
# ■ Code 1. adk create でプロジェクトを開始する
#   $ adk create support_agent
#   support_agent/
#   ├── __init__.py   # from . import agent
#   ├── agent.py      # root_agent を定義
#   └── .env          # API キーなどの設定
#   このフォルダ（m03_running_agent/）も同じ 3 ファイル構成です。
#
# ■ Code 3. 複数の agent を並べる
#   adk web に「親フォルダ」を渡すと、その中の agent フォルダが
#   左上のドロップダウンに並びます。
#   この agents/ フォルダ自体がその実例です：
#     agents/
#     ├── m01_adk/            ├── __init__.py / agent.py
#     ├── m02_configuring_agent/
#     └── m03_running_agent/  ...
#   $ cd agents && adk web .   → m01〜m13 を切り替えて試せる
# =====================================================================

import os

from google.adk import Agent

# 定数に切り出しておくと、Code 2 の比較コードが 1 行で読める
MODEL = os.environ.get("GEMINI_MODEL", "gemini-flash-latest")

INSTRUCTION = """You are a billing specialist for an online retailer.
Answer questions about account balances only.
Always call `lookup_account` before stating a balance.
If the tool returns status "error", say the account could not be found.
"""


def lookup_account(account_id: str) -> dict:
    """Returns the current balance and status for the given account.

    Args:
        account_id: The unique identifier for the customer account.

    Returns:
        dict: 'status' ("success" or "error"), and on success
              'balance' (float) and 'account_status' (str).
    """
    accounts = {
        "A-1001": {"balance": 128.50, "account_status": "active"},
        "A-1002": {"balance": 0.0, "account_status": "suspended"},
    }
    if account_id not in accounts:
        return {"status": "error", "message": f"Account {account_id} not found."}
    return {"status": "success", **accounts[account_id]}


# =====================================================================
# Code 2. root_agent という名前は変えられない
# ---------------------------------------------------------------------
# ✅ root_agent = Agent(...)   → adk web / adk run が見つけられる
# ❌ my_agent   = Agent(...)   → 「agent が見つかりません」で止まる
#
# 注意：name="billing_agent"（agent の名前）と、
#       変数名 root_agent（ADK が探す入口）は別物です。
#       name は自由に付けてよいが、変数名は root_agent 固定。
# =====================================================================
root_agent = Agent(  # ✅
    name="billing_agent",
    model=MODEL,
    instruction=INSTRUCTION,
    tools=[lookup_account],
)

# my_agent = Agent(name="billing_agent", model=MODEL, instruction=INSTRUCTION)  # ❌ runner が見つけられない


# =====================================================================
# Code 5. トレースビューを読む（このモジュールの本体）
# ---------------------------------------------------------------------
# adk web で「A-1001 の残高は？」と送ると、右側のトレースは次の形になる。
#
#   ユーザーメッセージ
#     └─ model 呼び出し #1
#          └─ function_call: lookup_account(account_id="A-1001")
#               └─ function_response: {"status": "success", "balance": 128.5}
#          └─ model 呼び出し #2
#               └─ 最終応答テキスト
#
# 期待どおりに動かないときは、このトレースで次の 3 つを切り分ける。
#   1. モデルが tool を「呼んでいない」      → docstring / instruction の問題
#   2. 呼んだが「引数が違う」                → 型ヒント / docstring の Args の問題
#   3. tool は正しいが「最終応答がおかしい」 → instruction の Rules の問題
#
# Code 6. 開発ループ
#   Write → Run → Test → Trace → Adjust →（Repeat）
#   agent.py を編集 → adk web → メッセージ送信 → トレース確認 → 修正
# =====================================================================
