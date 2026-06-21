"""App 全体に適用する Plugin。

Plugin は個々のエージェントに付ける callback と違い、**App 全体（すべての
エージェント・ツール・実行）に横断的に適用**されます。ロギングや計測といった
横断的関心事を 1 か所にまとめるのに向いています。

`BasePlugin` の各フックはすべてキーワード専用引数です。オーバーライドする際は
シグネチャを合わせます（不要なフックは実装しなくてかまいません）。
"""

from __future__ import annotations

from typing import Optional

from google.adk.agents import BaseAgent
from google.adk.agents.callback_context import CallbackContext
from google.adk.agents.invocation_context import InvocationContext
from google.adk.plugins import BasePlugin
from google.genai import types


class UsageLoggerPlugin(BasePlugin):
    """リサーチの進行（どのステージが動いたか）をログする Plugin。"""

    def __init__(self, name: str = "usage_logger") -> None:
        super().__init__(name=name)
        self._stages = 0

    async def on_user_message_callback(
        self, *, invocation_context: InvocationContext, user_message: types.Content
    ) -> Optional[types.Content]:
        """新しいユーザー依頼の受信時に呼ばれます。"""
        self._stages = 0
        print("[plugin] 新しいリサーチ依頼を受け付けました")
        return None

    async def before_agent_callback(
        self, *, agent: BaseAgent, callback_context: CallbackContext
    ) -> Optional[types.Content]:
        """各エージェント（パイプラインの各ステージ）の実行直前に呼ばれます。"""
        self._stages += 1
        print(f"[plugin] stage #{self._stages}: {agent.name} を実行します")
        return None

    async def after_run_callback(
        self, *, invocation_context: InvocationContext
    ) -> None:
        """1 回の実行（リサーチ全体）の完了時に呼ばれます。"""
        print(f"[plugin] リサーチ完了（実行ステージ数: {self._stages}）")
        return None
