"""ガードレール用のコールバック。

`before_model_callback` は LLM 呼び出しの直前に走り、`LlmResponse` を返すと
モデルを呼ばずにその応答へ差し替えられます。ここでは簡単なプロンプトインジェクション
対策として使います。
"""

from __future__ import annotations

from typing import Optional

from google.adk.agents.callback_context import CallbackContext
from google.adk.models import LlmRequest, LlmResponse
from google.genai import types

# 検知したら依頼を拒否する語（デモ用の簡易ブロックリスト）。
_BLOCKED_PHRASES = ("ignore previous", "これまでの指示を無視", "システムプロンプトを無視")


def _last_user_text(llm_request: LlmRequest) -> str:
    """LLM リクエストから直近のユーザー発話テキストを取り出します。"""
    for content in reversed(llm_request.contents or []):
        if content.role == "user":
            return " ".join(part.text or "" for part in (content.parts or []) if part.text)
    return ""


def block_unsafe_input(
    callback_context: CallbackContext, llm_request: LlmRequest
) -> Optional[LlmResponse]:
    """不審な指示（簡易なプロンプトインジェクション）を検知したら応答を差し替えます。"""
    text = _last_user_text(llm_request).lower()
    if any(phrase.lower() in text for phrase in _BLOCKED_PHRASES):
        print("[guardrail] 不審な指示を検知しました → リサーチを中止します")
        return LlmResponse(
            content=types.Content(
                role="model",
                parts=[types.Part(text="申し訳ありませんが、そのご依頼にはお応えできません。")],
            )
        )
    return None
