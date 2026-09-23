"""step_03_callbacks — コールバックで挙動を観察・制御する。

ADK には実行の前後に処理を差し込む 6 種類のコールバックがあります。本サンプルは
それぞれを 1 つずつ実装し、実用例（ロギング・ガードレール・キャッシュ）を示します。

  before_agent_callback / after_agent_callback   … エージェント実行の開始/終了
  before_model_callback  / after_model_callback   … モデル呼び出しの直前/直後
  before_tool_callback   / after_tool_callback    … ツール呼び出しの直前/直後

短絡（ショートサーキット）の仕組み:
  - before_model_callback が `LlmResponse` を返すと、モデル呼び出しをスキップして
    その応答を使います（= ガードレール）。
  - before_tool_callback が dict を返すと、ツール本体を呼ばずにその dict を結果として
    使います（= キャッシュやブロック）。
  - after_* で新しいオブジェクトを返すと、結果を差し替えられます。

例外処理の注意:
  ツールやコールバックの中で広い `except Exception:` / `except BaseException:` を書くと、
  ADK 2.x の自動リトライ（retry_config）や HITL（人間の確認）に必要な内部例外
  （NodeInterruptedError 等）まで握りつぶしてしまい、フレームワークの機能を壊します。
  捕捉は「想定済みの具体的な例外」だけにし、それ以外は素通しさせます。

注: 学習でコールバックの発火を「見える」ようにするため print を使っています。
    実運用では logging を使ってください。
"""

from __future__ import annotations

import os
from typing import Any, Optional

from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.models import LlmRequest, LlmResponse
from google.adk.tools.base_tool import BaseTool
from google.adk.tools.tool_context import ToolContext
from google.genai import types

MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")

# ガードレールでブロックする語（デモ用）。実際の入力に含まれていたら応答を差し替えます。
_BLOCKED_WORDS = ("パスワード", "password", "秘密鍵")

# 用語集ツールのデータ。
_GLOSSARY = {
    "agent": "ユーザーの目的を達成するために LLM やツールを制御する実行単位です。",
    "tool": "エージェントが呼び出せる関数や外部機能です。",
    "callback": "エージェント / モデル / ツールの実行前後に差し込む処理です。",
    "session": "一連の対話とその状態を保持する単位です。",
    "state": "セッション内で共有されるキーバリュー形式の作業メモリです。",
}


def _log(label: str, message: str) -> None:
    """コールバックの発火をターミナルに表示します（学習用）。"""
    print(f"[callback:{label}] {message}")


# --- Tool ------------------------------------------------------------------


def lookup_term(term: str) -> dict:
    """ADK の用語集から用語の意味を引きます。

    Args:
        term: 調べたい用語（例: "agent", "tool", "callback", "session", "state"）。

    Returns:
        status と、成功時は term・definition、失敗時は error_message を含む dict。
    """
    key = term.strip().lower()
    definition = _GLOSSARY.get(key)
    if definition is None:
        return {
            "status": "error",
            "error_message": f"用語 '{term}' は用語集に登録されていません。",
        }
    return {"status": "success", "term": key, "definition": definition}


# --- Agent callbacks（ロギング）---------------------------------------------


def log_before_agent(callback_context: CallbackContext) -> Optional[types.Content]:
    """エージェント実行開始をログし、リクエスト回数を state に記録します。"""
    count = int(callback_context.state.get("request_count", 0)) + 1
    callback_context.state["request_count"] = count
    _log("before_agent", f"agent={callback_context.agent_name} 開始 (このセッション {count} 回目)")
    # None を返すと通常どおりエージェントを実行します。
    # types.Content を返すとエージェント本体をスキップし、その内容を応答にできます。
    return None


def log_after_agent(callback_context: CallbackContext) -> Optional[types.Content]:
    """エージェント実行終了をログします。"""
    _log("after_agent", f"agent={callback_context.agent_name} 終了 (invocation={callback_context.invocation_id})")
    return None


# --- Model callbacks（ガードレール / ロギング）------------------------------


def _last_user_text(llm_request: LlmRequest) -> str:
    """LLM へ渡すリクエストから、直近のユーザー発話テキストを取り出します。"""
    for content in reversed(llm_request.contents or []):
        if content.role == "user":
            return " ".join(part.text or "" for part in (content.parts or []) if part.text)
    return ""


def guardrail_before_model(
    callback_context: CallbackContext, llm_request: LlmRequest
) -> Optional[LlmResponse]:
    """入力に NG ワードが含まれていたら、モデルを呼ばずに定型応答へ差し替えます。"""
    user_text = _last_user_text(llm_request)
    hit = next((w for w in _BLOCKED_WORDS if w in user_text), None)
    if hit is not None:
        _log("before_model", f"ガードレール作動: NG ワード '{hit}' を検知 → モデル呼び出しをスキップ")
        # LlmResponse を返すと、モデル呼び出しをスキップしてこの応答を使います。
        return LlmResponse(
            content=types.Content(
                role="model",
                parts=[types.Part(text="申し訳ありませんが、その内容にはお答えできません。")],
            )
        )
    _log("before_model", "入力チェック OK → モデルを呼び出します")
    return None


def log_after_model(
    callback_context: CallbackContext, llm_response: LlmResponse
) -> Optional[LlmResponse]:
    """モデル応答のトークン使用量などをログします。"""
    # ストリーミングの途中チャンク（partial）は無視し、確定応答だけを対象にします。
    if llm_response.partial:
        return None
    usage = llm_response.usage_metadata
    if usage is not None:
        _log("after_model", f"応答を受信 (total_token_count={usage.total_token_count})")
    else:
        _log("after_model", "応答を受信")
    # ここで新しい LlmResponse を返すと応答本文を差し替えられます（今回はログのみ）。
    return None


# --- Tool callbacks（キャッシュ / 注釈）-------------------------------------


def cache_before_tool(
    tool: BaseTool, args: dict[str, Any], tool_context: ToolContext
) -> Optional[dict]:
    """同じ引数で呼ばれたことがあれば、ツールを実行せずキャッシュを返します。"""
    cache = tool_context.state.get("tool_cache") or {}
    key = f"{tool.name}:{sorted(args.items())}"
    if key in cache:
        _log("before_tool", f"キャッシュ命中 ({tool.name}) → ツール実行をスキップ")
        # dict を返すと、ツール本体を呼ばずにこの dict を結果として使います。
        return {**cache[key], "cache": "hit"}
    _log("before_tool", f"キャッシュなし ({tool.name}) → ツールを実行")
    return None


def annotate_after_tool(
    tool: BaseTool,
    args: dict[str, Any],
    tool_context: ToolContext,
    tool_response: dict,
) -> Optional[dict]:
    """ツール結果をキャッシュに保存し、結果に注釈を付けて差し替えます。"""
    cache = dict(tool_context.state.get("tool_cache") or {})
    key = f"{tool.name}:{sorted(args.items())}"
    cache[key] = tool_response
    tool_context.state["tool_cache"] = cache
    _log("after_tool", f"結果をキャッシュに保存 ({tool.name})")
    # 新しい dict を返すと結果を差し替えられます（元の引数は変更しません = イミュータブル）。
    return {**tool_response, "cache": "miss"}


# --- Agent -----------------------------------------------------------------

root_agent = Agent(
    name="callback_demo_agent",
    model=MODEL,
    description="6 種類のコールバックの動作を観察するための用語集エージェント。",
    instruction=(
        "あなたは ADK の用語を説明するアシスタントです。"
        "用語の意味を聞かれたら lookup_term を使って答えてください。"
        "それ以外の話題には一般知識で簡潔に答えてください。"
    ),
    tools=[lookup_term],
    before_agent_callback=log_before_agent,
    after_agent_callback=log_after_agent,
    before_model_callback=guardrail_before_model,
    after_model_callback=log_after_model,
    before_tool_callback=cache_before_tool,
    after_tool_callback=annotate_after_tool,
    # 2.x の新しいエラー用フックもあります（今回は未使用、コメントで紹介）:
    #   on_model_error_callback(ctx, llm_request, error) -> Optional[LlmResponse]
    #   on_tool_error_callback(tool, args, ctx, error) -> Optional[dict]
)
