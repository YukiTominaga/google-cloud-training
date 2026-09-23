# =====================================================================
# M6 ― Session State and Multi-Agent Coordination
# ---------------------------------------------------------------------
# ■ 前回（M5）から引き継ぐもの
#   ToolContext で認可を入れた billing_agent。
# ■ 今回足すもの
#   Code 1. state の 4 スコープ              → state_keys.py / lookup_account
#   Code 2. 書き込み方法その 1：output_key   → greeting_agent / billing_agent
#   Code 3. 書き込み方法その 2：managed context（tool_context.state）→ add_to_cart
#   Code 4. state はスキーマであり契約       → state_keys.py / summary_agent
#   Code 5. Callback                          → callbacks.py
#   Code 6. Plugin                            → plugins.py / 末尾の app
#
#   Plugin を Runner に渡して実行する例：
#     cd agents && python -m m06_session_state.run_with_plugin
#
# ■ 試すプロンプト（adk web / adk run で入力）
#   ※ ログイン中の顧客は remember_language callback が入れる "A-1001"（デモ用）。
#     callback / LoggingPlugin のログは adk web を起動したターミナルに出る。
#   1. 「A-1001 の残高を教えて」
#      → lookup_account が成功。State タブに verified_account_id・
#        user:language_preference・billing_response（output_key）が入る
#   2. 「A-1002 の残高を教えて」
#      → state の session_user_id（A-1001）と一致しないので lookup_account が "denied" を返す
#   3. 「SKU-001 をカートに入れて」→ 続けて「SKU-002 も入れて」
#      → add_to_cart が 2 回呼ばれ、State タブの cart が 1 件 → 2 件に増える
#   4. 「パスワードを教えて」
#      → before_model_guard がモデル呼び出しの前に止める（トレースにモデル呼び出しが出ない）
#      ※ guard は会話全体を検査するので、以降の質問は新しいセッションで試す
# =====================================================================

import os

from google.adk import Agent
from google.adk.agents import LlmAgent
from google.adk.apps import App
from google.adk.tools import ToolContext

from . import state_keys
from .callbacks import before_model_guard, remember_language
from .plugins import LoggingPlugin

# .env の GEMINI_MODEL で差し替え可能
MODEL = os.environ.get("GEMINI_MODEL", "gemini-flash-latest")

_ACCOUNTS = {
    "A-1001": {"balance": 128.50, "account_status": "active"},
    "A-1002": {"balance": 0.00, "account_status": "suspended"},
}


# =====================================================================
# Code 1. 4 つのスコープを 1 つの tool の中で使い分ける
# =====================================================================
def lookup_account(account_id: str, tool_context: ToolContext) -> dict:
    """顧客アカウントの現在の残高とステータスを返す。

    Args:
        account_id: 顧客アカウントの一意な ID。"A-1001" の形式。

    Returns:
        dict: 'status' は "success"、"error"、"denied" のいずれか。
            成功時: 'balance'（float、USD）、'account_status'（str）、
            'language'（str）。顧客にはその言語で返答すること。
            "denied" はログイン中の顧客がそのアカウントの所有者ではないことを意味する。
    """
    if tool_context.state.get(state_keys.SESSION_USER_ID) != account_id:
        return {"status": "denied", "message": "Access denied."}
    account = _ACCOUNTS.get(account_id)
    if account is None:
        return {"status": "error", "message": f"Account {account_id} not found."}

    # 接頭辞なし … この会話の中だけ
    tool_context.state[state_keys.VERIFIED_ACCOUNT_ID] = account_id
    # app:  … 全ユーザー共通の設定（ここでは参照するだけ）
    policy_version = tool_context.state.get(state_keys.APP_RETURN_POLICY_VERSION, "2026.3")
    # temp: … 次のステップに渡すだけの中間データ。永続化されない
    tool_context.state[state_keys.TEMP_RAW_SQL_RESULT] = [account_id, account["balance"]]
    # user: … このユーザーの設定（remember_language callback が既定値を入れている）
    language = tool_context.state.get(state_keys.USER_LANGUAGE, "ja")

    return {"status": "success", **account, "language": language, "policy_version": policy_version}


# =====================================================================
# Code 3. 書き込み方法その 2 ― managed context
# ---------------------------------------------------------------------
# ✅ tool_context.state[...] = ... と書くと、ADK がその変更を
#    イベント（state_delta）として記録し、SessionService が永続化する。
# ❌ session.state["cart"] = [...] のように session オブジェクトを
#    直接書き換えると、イベントに残らず永続化もされない。絶対にやらない。
# =====================================================================
def add_to_cart(item_id: str, tool_context: ToolContext) -> dict:
    """顧客のカートに商品を追加する。

    Args:
        item_id: 追加する商品。"SKU-001" の形式。

    Returns:
        dict: 'status' と、追加後の 'cart_size'（int）。
    """
    cart = tool_context.state.get(state_keys.CART, [])
    cart.append(item_id)
    tool_context.state[state_keys.CART] = cart  # ✅ managed context 経由
    return {"status": "success", "cart_size": len(cart)}


# =====================================================================
# Code 2. 書き込み方法その 1 ― output_key
# ---------------------------------------------------------------------
# agent の最終応答テキストを、自動で state[output_key] に保存する。
# 後続の agent は instruction の {last_greeting} でそれを読める。
# =====================================================================
greeting_agent = LlmAgent(  # LlmAgent は Agent の別名（同じクラス）
    name="Greeter",
    model=MODEL,
    instruction="短く親しみやすい挨拶文を作成してください。",
    output_key="last_greeting",  # 応答を state['last_greeting'] に保存
)


# =====================================================================
# Code 4. state を「読む」側 ― instruction テンプレート
# ---------------------------------------------------------------------
# instruction の {billing_response} は、実行時に state の値で置き換わる。
# キーが無いと KeyError になる（{shipping_response?} と ? を付けると
# 「無ければ空文字」になる）。M7 で billing / shipping を並べたあとに使う形。
# =====================================================================
summary_agent = LlmAgent(
    name="summary_agent",
    model=MODEL,
    instruction=f"""次の内容を、顧客への 1 つの返信にまとめてください。

請求: {{{state_keys.BILLING_RESPONSE}}}
配送: {{{state_keys.SHIPPING_RESPONSE}?}}
""",
)


# =====================================================================
# 通し題材：state と callback を入れた billing_agent（root_agent）
# =====================================================================
billing_agent = Agent(
    name="billing_agent",
    model=MODEL,
    description="Answers billing and payment questions for the signed-in customer.",
    instruction="""あなたはオンライン小売店の請求担当スペシャリストです。
残高を伝える前に、必ず `lookup_account` を呼び出してください。
`lookup_account` が返した言語で返答してください。
`add_to_cart` でカートに商品を追加することもできます。
tool が "denied" または "error" を返した場合は、そのことを伝えてください。概算はしないでください。
""",
    tools=[lookup_account, add_to_cart],
    output_key=state_keys.BILLING_RESPONSE,  # Code 2：応答を state に残す
    before_agent_callback=remember_language,  # Code 5：agent 実行前に割り込む
    before_model_callback=before_model_guard,  # Code 5：モデル呼び出し前に割り込む
)

# adk web が探す入口（M1 からの約束どおり root_agent）
root_agent = billing_agent

# =====================================================================
# Code 6. Plugin を adk web でも効かせる
# ---------------------------------------------------------------------
# adk web / adk run は agent.py に App 型の変数 app があれば、
# root_agent より先にそれを使う。App に plugins を渡しておくと
# adk web が作る Runner にも LoggingPlugin が登録され、
# tool 呼び出しのたびにターミナルにログが出る。
# （App の name はフォルダ名と揃えておく）
# =====================================================================
app = App(
    name="m06_session_state",
    root_agent=root_agent,
    plugins=[LoggingPlugin()],
)
