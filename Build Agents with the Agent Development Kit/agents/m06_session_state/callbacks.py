# =====================================================================
# M6 Code 5. Callback ― 実行の要所に割り込む
# ---------------------------------------------------------------------
# agent 単位で「実行の要所」に関数を差し込めます。チェックポイントは 6 つ。
#   before_agent_callback / after_agent_callback
#   before_model_callback / after_model_callback   ← 本ファイルの例
#   before_tool_callback  / after_tool_callback
# （ADK 2.9.2 では on_model_error_callback / on_tool_error_callback も追加）
#
# ■ 戻り値のルール（全 callback 共通）
#   None を返す      → 何もしない。通常どおり処理を続ける
#   None 以外を返す  → 本来の処理をスキップし、その値を結果として使う
# =====================================================================

from typing import Optional

from google.adk.agents.callback_context import CallbackContext
from google.adk.models import LlmRequest, LlmResponse
from google.genai import types

from . import state_keys


def before_model_guard(
    callback_context: CallbackContext,
    llm_request: LlmRequest,
) -> Optional[LlmResponse]:
    """認証情報を尋ねるリクエストを、モデルに届く前にブロックする。"""
    # llm_request.contents はこれからモデルに送る会話全体。
    # テキスト部分だけをつなげて検査する。
    text = ""
    for content in llm_request.contents or []:
        for part in content.parts or []:
            if part.text:
                text += part.text

    if "password" in text.lower() or "パスワード" in text:
        # None 以外を返す = モデル呼び出しをスキップしてこの応答を返す
        # （モデルに届く前に止めるので、プロンプトで頼むより確実）
        return LlmResponse(
            content=types.Content(
                role="model",
                parts=[types.Part(text="セキュリティ上、その情報はお答えできません。")],
            )
        )
    return None  # None を返す = 通常どおりモデルを呼ぶ


def remember_language(callback_context: CallbackContext) -> Optional[types.Content]:
    """before_agent_callback の例：user スコープの既定値を用意する。

    user: で始まるキーは「このユーザーの全セッション」で共有される。
    初回だけ既定値を入れ、2 回目以降は既存の値を尊重する。
    """
    if callback_context.state.get(state_keys.USER_LANGUAGE) is None:
        callback_context.state[state_keys.USER_LANGUAGE] = "ja"
    # デモ用のログイン状態（M5 と同じ。本来はアプリが入れる値）
    if callback_context.state.get(state_keys.SESSION_USER_ID) is None:
        callback_context.state[state_keys.SESSION_USER_ID] = "A-1001"
    return None
