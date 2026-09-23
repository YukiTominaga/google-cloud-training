# =====================================================================
# M9 Code 5. 階層の制約と AgentTool
# ---------------------------------------------------------------------
# ■ 階層の制約
#   Agent は親を 1 つしか持てない。agent.py の billing_agent は
#   support_coordinator の子なので、別の agent の sub_agents には入れられない。
#
# ■ AgentTool：agent を「tool として」呼ぶ
#   ・sub_agents（委譲）… 会話の制御が子に移る
#   ・AgentTool（道具）… 呼んだ側が制御を持ったまま、子の結果だけ受け取る
#                        （関数 tool を呼ぶのと同じ感覚）
#   → 「残高の数字だけ欲しい」ような場面は AgentTool が向いている。
#
# adk web には読み込まれません（講義で見せるための例）。
# =====================================================================

import os

from google.adk import Agent
from google.adk.tools import AgentTool

from .tools import list_invoices, lookup_account

MODEL = os.environ.get("GEMINI_MODEL", "gemini-flash-latest")

# AgentTool で包む agent は、どこの sub_agents にも入っていない
# 独立したインスタンスとして用意する（親を持たない）
billing_tool_agent = Agent(
    name="billing_agent",
    model=MODEL,
    # AgentTool では description が「tool の説明」としてモデルに渡る
    description="Looks up an account and returns its balance and recent invoices.",
    instruction="Look up the account and summarize the billing situation in one sentence.",
    tools=[lookup_account, list_invoices],
)

triage_agent = Agent(
    name="triage_agent",
    model=MODEL,
    instruction="Use the billing_agent tool when you need a balance figure.",
    tools=[AgentTool(agent=billing_tool_agent)],  # ← agent を tool として渡す
)
