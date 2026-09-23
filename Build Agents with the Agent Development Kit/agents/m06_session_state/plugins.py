# =====================================================================
# M6 Code 6. Plugin ― runner レベルで一律に効かせる
# ---------------------------------------------------------------------
# Callback は「agent ごと」に付けるもの。
# Plugin は「Runner に 1 回登録すれば、配下のすべての agent / tool /
# モデル呼び出しに一律で効く」もの。
# ログ・監査・ガードレールのような横断的関心事は Plugin に置く。
#
# ※ BasePlugin には agent / model / tool の callback のほか、
#   before_run_callback / after_run_callback / on_user_message_callback /
#   on_event_callback / 各種 on_*_error_callback もある。
# =====================================================================

from typing import Any, Optional

from google.adk.plugins import BasePlugin
from google.adk.tools import BaseTool, ToolContext


class LoggingPlugin(BasePlugin):
    """すべての tool 呼び出しを標準出力に記録する Plugin。"""

    def __init__(self) -> None:
        # name は Plugin の識別子（ログ等に出る）
        super().__init__(name="logging")

    async def before_tool_callback(
        self,
        *,
        tool: BaseTool,
        tool_args: dict[str, Any],
        tool_context: ToolContext,
    ) -> Optional[dict]:
        # どの agent が、どの tool を、どの引数で呼んだか
        print(f"[{tool_context.agent_name}] [{tool.name}] called with {tool_args}")
        return None  # None = tool を通常どおり実行する（Callback と同じ約束）

    async def after_tool_callback(
        self,
        *,
        tool: BaseTool,
        tool_args: dict[str, Any],
        tool_context: ToolContext,
        result: dict,
    ) -> Optional[dict]:
        print(f"[{tool.name}] returned {result}")
        return None  # None = 結果を書き換えない
