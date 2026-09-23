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
#
# ■ 試すプロンプト（adk web / adk run で入力）
#   1. 「A-1001 の残高は？」
#      → トレースが function_call lookup_account(account_id="A-1001")
#        → function_response（balance 128.5）→ 最終応答 の形になるか確認する（Code 5）
#   2. 「A-1002 の残高と状態を教えて」
#      → lookup_account が呼ばれ、残高 0.0 と状態 suspended が返る
#   3. 「A-9999 の残高は？」
#      → lookup_account が status "error" を返し、見つからなかったと伝える
#   4. 「A-1001 の請求書を一覧して」
#      → 残高以外は対応範囲外で、請求書を取る tool も無い。
#        トレースで tool が呼ばれたか・どう断ったかを確認する
# =====================================================================

import os

from google.adk import Agent

# 定数に切り出しておくと、Code 2 の比較コードが 1 行で読める
MODEL = os.environ.get("GEMINI_MODEL", "gemini-flash-latest")

INSTRUCTION = """あなたはオンライン小売店の請求担当スペシャリストです。
アカウント残高に関する質問にだけ答えてください。
残高を伝える前に、必ず `lookup_account` を呼び出してください。
tool が status "error" を返した場合は、アカウントが見つからなかったと伝えてください。
"""


def lookup_account(account_id: str) -> dict:
    """指定したアカウントの現在の残高とステータスを返す。

    Args:
        account_id: 顧客アカウントの一意な ID。

    Returns:
        dict: 'status'（"success" または "error"）。成功時は
              'balance'（float）と 'account_status'（str）も含む。
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
