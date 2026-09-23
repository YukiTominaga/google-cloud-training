# =====================================================================
# M6 Code 6. Plugin を Runner に登録して実行する
# ---------------------------------------------------------------------
# 実行方法（agents/ フォルダで。GOOGLE_API_KEY が必要）:
#   python -m m06_session_state.run_with_plugin
#
# 見せたいポイント
#   ・plugins=[...] は Runner の引数 ＝ 配下の全 agent に一律で効く
#   ・同じ user_id で 2 つ目のセッションを作ると、user: スコープの値は
#     引き継がれ、接頭辞なしの値は引き継がれない
# =====================================================================

import asyncio

from dotenv import load_dotenv
from google.adk.runners import InMemoryRunner
from google.genai import types

# agent の import より先に読む（MODEL が GEMINI_MODEL を参照するため）
load_dotenv()

from . import state_keys  # noqa: E402
from .agent import root_agent  # noqa: E402
from .plugins import LoggingPlugin  # noqa: E402

APP_NAME = "support_app"
USER_ID = "customer-42"


async def ask(runner: InMemoryRunner, session_id: str, text: str) -> None:
    """1 往復して最終応答テキストだけを表示する。"""
    message = types.Content(role="user", parts=[types.Part(text=text)])
    async for event in runner.run_async(
        user_id=USER_ID, session_id=session_id, new_message=message
    ):
        if event.is_final_response() and event.content and event.content.parts:
            print("agent>", "".join(p.text or "" for p in event.content.parts))


async def main() -> None:
    runner = InMemoryRunner(
        agent=root_agent,
        app_name=APP_NAME,
        plugins=[LoggingPlugin()],  # ← runner レベルで一律に効かせる
    )

    # --- セッション 1 ---
    s1 = await runner.session_service.create_session(
        app_name=APP_NAME,
        user_id=USER_ID,
        state={
            state_keys.SESSION_USER_ID: "A-1001",
            state_keys.USER_LANGUAGE: "en",  # user: スコープ
        },
    )
    await ask(runner, s1.id, "What is the balance of A-1001?")

    # --- セッション 2（同じユーザー）---
    s2 = await runner.session_service.create_session(app_name=APP_NAME, user_id=USER_ID)
    s2 = await runner.session_service.get_session(
        app_name=APP_NAME, user_id=USER_ID, session_id=s2.id
    )
    print(
        "session 2 の user:language_preference =", s2.state.get(state_keys.USER_LANGUAGE)
    )  # en が引き継がれる
    print(
        "session 2 の verified_account_id     =", s2.state.get(state_keys.VERIFIED_ACCOUNT_ID)
    )  # None


if __name__ == "__main__":
    asyncio.run(main())
