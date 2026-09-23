# =====================================================================
# M11 Code 3. ローカルからプラットフォームへ ― 差し替えるのは runner だけ
# ---------------------------------------------------------------------
# 同じ root_agent を、2 通りの Runner で動かせることを見せる。
#
#   ローカル開発      : InMemoryRunner（全部メモリ上。プロセス終了で消える）
#   プラットフォーム  : Runner ＋ VertexAiSessionService（短期記憶）
#                              ＋ VertexAiMemoryBankService（長期記憶）
#
# 実行方法（agents/ フォルダで）:
#   python -m m11_platform.runners local      # API キーだけで動く
#   python -m m11_platform.runners platform   # Agent Runtime（reasoningEngine）が必要
#
# platform モードでは環境変数で接続先を渡す：
#   export GOOGLE_CLOUD_PROJECT=my-project
#   export GOOGLE_CLOUD_LOCATION=us-central1
#   export AGENT_ENGINE_ID=1234567890   # M12 のデプロイで得られる数値 ID
# =====================================================================

import asyncio
import os
import sys

from dotenv import load_dotenv
from google.adk.runners import InMemoryRunner, Runner
from google.genai import types

# agent の import より先に読む（MODEL が GEMINI_MODEL を参照するため）
load_dotenv()

from .agent import root_agent  # noqa: E402  ← agent 側は 1 行も変えない

APP_NAME = "support_app"


# ---------------------------------------------------------------------
# ① ローカル開発
# ---------------------------------------------------------------------
def build_local_runner() -> Runner:
    return InMemoryRunner(agent=root_agent, app_name=APP_NAME)


# ---------------------------------------------------------------------
# ② プラットフォームのマネージドサービスに接続する
# ---------------------------------------------------------------------
def build_platform_runner() -> Runner:
    # import を関数内に置くのは、ローカル実行時に Cloud の認証情報を
    # 要求しないようにするため（説明の本筋とは関係ない）
    from google.adk.memory import VertexAiMemoryBankService
    from google.adk.sessions import VertexAiSessionService

    project = os.environ["GOOGLE_CLOUD_PROJECT"]
    location = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
    agent_engine_id = os.environ["AGENT_ENGINE_ID"]

    # 短期記憶：会話の流れをマネージドサービスが保持する
    session_service = VertexAiSessionService(
        project=project,
        location=location,
        agent_engine_id=agent_engine_id,
    )
    # 長期記憶：ユーザーの嗜好や事実を抽出して数週間〜数か月保存する
    memory_service = VertexAiMemoryBankService(
        project=project,
        location=location,
        agent_engine_id=agent_engine_id,
    )
    # 差し替えるのはここだけ。agent=root_agent は ① と同じ
    return Runner(
        agent=root_agent,
        app_name=APP_NAME,
        session_service=session_service,
        memory_service=memory_service,
    )


async def chat(runner: Runner, user_id: str, text: str) -> None:
    """新しいセッションを作って 1 往復する。"""
    session = await runner.session_service.create_session(app_name=APP_NAME, user_id=user_id)
    message = types.Content(role="user", parts=[types.Part(text=text)])
    async for event in runner.run_async(
        user_id=user_id, session_id=session.id, new_message=message
    ):
        if event.is_final_response() and event.content and event.content.parts:
            print("agent>", "".join(p.text or "" for p in event.content.parts))


async def main(mode: str) -> None:
    runner = build_platform_runner() if mode == "platform" else build_local_runner()
    # 1 回目のセッションで口座番号を伝え、2 回目の「別の」セッションで思い出せるか試す
    await chat(runner, "customer-42", "My account ID is A-1001. Please remember it.")
    await chat(runner, "customer-42", "What is my balance?")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "local"))
