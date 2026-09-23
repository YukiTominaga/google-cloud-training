"""step_04_multi_agent / workflows.py — ワークフローエージェントと Custom 分岐の最小例。

agent.py の「階層型転送」が LLM の判断で動く（自律的）のに対し、ここで扱う
ワークフローエージェントは **制御フローが決定的** です。用途に応じて使い分けます。

  - SequentialAgent : sub_agents を上から順番に実行（パイプライン）
  - ParallelAgent   : sub_agents を並列に実行（ファンアウト）
  - LoopAgent       : sub_agents を繰り返し実行（max_iterations か exit_loop で停止）
  - Custom(BaseAgent): _run_async_impl を書いて条件分岐・動的選択を自作

各段の結果は `output_key` で session state に保存され、後続エージェントは instruction 内の
`{key}` でそれを参照できます。

このファイルは自己完結しており、そのまま実行できます（モデルへのアクセスが必要です）:

    uv run python step_04_multi_agent/workflows.py
"""

from __future__ import annotations

import asyncio
import os
from typing import AsyncGenerator, Optional

from google.adk.agents import (
    BaseAgent,
    LlmAgent,
    LoopAgent,
    ParallelAgent,
    SequentialAgent,
)
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.adk.runners import InMemoryRunner
from google.adk.tools import exit_loop
from dotenv import load_dotenv
from google.genai import types

# adk CLI 以外（このスクリプトを直接実行する場合）でも、リポジトリ直下の .env を読み込みます。
load_dotenv()

MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")
APP_NAME = "workflow_demo"


# --- 1. SequentialAgent（順次パイプライン）---------------------------------


def build_sequential() -> SequentialAgent:
    outliner = LlmAgent(
        name="outliner",
        model=MODEL,
        description="テーマから箇条書きのアウトラインを作る。",
        instruction="与えられたテーマについて、箇条書きのアウトラインを 3 点だけ作ってください。",
        output_key="outline",  # 結果を state["outline"] に保存
    )
    writer = LlmAgent(
        name="writer",
        model=MODEL,
        description="アウトラインを短い文章に展開する。",
        # instruction 内の {outline} は前段が state に書いた値で置き換わります。
        instruction="次のアウトラインを 3 文程度の文章に展開してください:\n{outline}",
        output_key="article",
    )
    return SequentialAgent(name="sequential_pipeline", sub_agents=[outliner, writer])


# --- 2. ParallelAgent（並列ファンアウト）-----------------------------------


def build_parallel() -> ParallelAgent:
    pros = LlmAgent(
        name="pros_writer",
        model=MODEL,
        description="テーマの利点を挙げる。",
        instruction="与えられたテーマの利点を 3 つ、箇条書きで挙げてください。",
        output_key="pros",
    )
    cons = LlmAgent(
        name="cons_writer",
        model=MODEL,
        description="テーマの欠点を挙げる。",
        instruction="与えられたテーマの欠点を 3 つ、箇条書きで挙げてください。",
        output_key="cons",
    )
    # pros と cons は並列に実行され、それぞれ別の output_key に書き込みます。
    return ParallelAgent(name="parallel_fanout", sub_agents=[pros, cons])


# --- 3. LoopAgent（反復改善）-----------------------------------------------


def build_loop() -> LoopAgent:
    refiner = LlmAgent(
        name="slogan_refiner",
        model=MODEL,
        description="スローガンを 1 つ作る / 改善する。",
        # {slogan?} は「あれば差し込む」optional 参照。初回は未設定でも動きます。
        instruction=(
            "与えられたテーマのキャッチコピーを 1 つ作ってください。"
            "前回案がある場合はそれを改善してください: {slogan?}"
        ),
        output_key="slogan",
    )
    quality_gate = LlmAgent(
        name="quality_gate",
        model=MODEL,
        description="スローガンが十分なら停止を指示する。",
        instruction=(
            "次のスローガンが十分にキャッチーで短いなら、exit_loop ツールを呼んで"
            "ループを終了してください。まだ改善余地があるなら『改善が必要』とだけ答えてください。\n"
            "スローガン: {slogan}"
        ),
        tools=[exit_loop],  # ループ脱出用の組み込みツール
    )
    # max_iterations で必ず上限回数に達したら止まります（暴走防止）。
    return LoopAgent(
        name="loop_refine",
        max_iterations=3,
        sub_agents=[refiner, quality_gate],
    )


# --- 4. Custom（BaseAgent を継承して条件分岐）------------------------------


class TopicRouter(BaseAgent):
    """state["topic"] に応じて、担当の子エージェントへ動的に分岐するカスタムエージェント。"""

    # 子エージェントを型付きフィールドとして宣言します。
    tech: LlmAgent
    general: LlmAgent
    model_config = {"arbitrary_types_allowed": True}

    def __init__(self, name: str, tech: LlmAgent, general: LlmAgent):
        # sub_agents にも渡してフレームワークに親子関係を認識させます。
        super().__init__(name=name, tech=tech, general=general, sub_agents=[tech, general])

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        # session state を読んで、実行する子エージェントを動的に選びます。
        topic = ctx.session.state.get("topic", "general")
        chosen = self.tech if topic == "tech" else self.general
        print(f"[TopicRouter] topic={topic!r} → {chosen.name} に委譲します")
        # 選んだ子の run_async をそのまま中継します。
        async for event in chosen.run_async(ctx):
            yield event


def build_custom() -> TopicRouter:
    tech = LlmAgent(
        name="tech_answer",
        model=MODEL,
        description="技術的な質問に答える。",
        instruction="技術サポート担当として、簡潔に回答してください。",
    )
    general = LlmAgent(
        name="general_answer",
        model=MODEL,
        description="一般的な質問に答える。",
        instruction="総合窓口として、簡潔に回答してください。",
    )
    return TopicRouter(name="topic_router", tech=tech, general=general)


# --- 実行ヘルパ ------------------------------------------------------------


async def run_demo(
    title: str,
    agent: BaseAgent,
    prompt: str,
    initial_state: Optional[dict] = None,
) -> None:
    """1 つのワークフローエージェントを InMemoryRunner で実行し、最終応答を表示します。"""
    print(f"\n===== {title} =====")
    runner = InMemoryRunner(agent=agent, app_name=APP_NAME)
    await runner.session_service.create_session(
        app_name=APP_NAME, user_id="u", session_id="s", state=initial_state or {}
    )
    message = types.Content(role="user", parts=[types.Part(text=prompt)])
    async for event in runner.run_async(user_id="u", session_id="s", new_message=message):
        # ストリーミングの途中チャンク（partial）は飛ばし、確定した本文だけ表示します。
        if event.partial or not (event.content and event.content.parts):
            continue
        text = "".join(part.text or "" for part in event.content.parts if part.text)
        if text.strip():
            print(f"[{event.author}] {text.strip()}")


async def main() -> None:
    await run_demo("1. SequentialAgent（順次）", build_sequential(), "テーマ: リモートワーク")
    await run_demo("2. ParallelAgent（並列）", build_parallel(), "テーマ: リモートワーク")
    await run_demo("3. LoopAgent（反復）", build_loop(), "テーマ: 新しいカフェ")
    await run_demo(
        "4. Custom BaseAgent（条件分岐）",
        build_custom(),
        "PC が起動しません",
        initial_state={"topic": "tech"},
    )


if __name__ == "__main__":
    asyncio.run(main())
