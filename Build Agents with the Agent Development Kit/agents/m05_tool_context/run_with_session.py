# =====================================================================
# M5 Code 5（後半）. Runner から state を渡して実行する
# ---------------------------------------------------------------------
# adk web を使わず、Python から直接 agent を動かす例です。
# ここで初めて Runner を自分で書きますが、目的は 1 つだけ：
#   「session_user_id はアプリが入れる。LLM は触れない」を見せること。
#
# 実行方法（agents/ フォルダで。GOOGLE_API_KEY が必要）:
#   python -m m05_tool_context.run_with_session
#
# 期待される結果：
#   A-1001 でログインした顧客が「A-1002 の残高は？」と聞く
#   → lookup_account が "denied" を返し、agent は金額を明かさずに断る
# =====================================================================

import asyncio

from dotenv import load_dotenv
from google.adk.runners import InMemoryRunner
from google.genai import types

# adk web / adk run は .env を自動で読むが、自前スクリプトでは自分で読む
# agent の import より先に読む（MODEL が GEMINI_MODEL を参照するため）
load_dotenv()

from .agent import root_agent  # noqa: E402

APP_NAME = "support_app"
USER_ID = "customer-42"


async def main() -> None:
    # InMemoryRunner：session / artifact / memory をすべてメモリ上に持つ Runner。
    # ローカル実験用（プロセスが終わると全部消える）。M11 で差し替える部分。
    runner = InMemoryRunner(agent=root_agent, app_name=APP_NAME)

    # セッション作成時に初期 state を渡す。
    # ここがログイン処理を終えたアプリの役割 ＝ 信頼できる値の出どころ。
    session = await runner.session_service.create_session(
        app_name=APP_NAME,
        user_id=USER_ID,
        state={"session_user_id": "A-1001"},  # ← アプリが入れる。LLM は触れない
    )

    # 他人の口座（A-1002）を聞いてみる
    message = types.Content(role="user", parts=[types.Part(text="A-1002 の残高は？")])

    # run_async はイベント（モデル応答・tool 呼び出し・tool 結果…）を順に返す
    async for event in runner.run_async(
        user_id=USER_ID, session_id=session.id, new_message=message
    ):
        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.function_call:  # モデルが tool を呼んだ
                    print(f"[tool call] {part.function_call.name}({part.function_call.args})")
                elif part.function_response:  # tool が結果を返した
                    print(f"[tool result] {part.function_response.response}")
                elif part.text:  # モデルのテキスト応答
                    print(part.text, end="")
    print()


if __name__ == "__main__":
    asyncio.run(main())
