"""step_04_multi_agent — 階層型マルチエージェント（転送 / transfer）。

このファイルの `root_agent` は「受付（coordinator）」で、問い合わせ内容に応じて
専門の担当エージェント（sub_agents）へ **転送（transfer / delegation）** します。

ポイント:
  - `sub_agents=[...]` を渡すと、ADK は LLM が `transfer_to_agent` を呼べるように
    自動でお膳立てします。LLM は各 sub-agent の **description** を読んで「誰に
    任せるか」を判断します。だから description は転送の精度に直結します。
  - 転送は「制御そのものを子へ渡す」動きです（AgentTool が『呼んで結果を受け取る』
    のとは対照的。step_02_agent_with_tools を参照）。
  - `disallow_transfer_to_parent=True` / `disallow_transfer_to_peers=True` を子に
    設定すると、その子からの戻り/横移動を禁止できます（今回は既定のまま）。

ワークフローエージェント（Sequential/Parallel/Loop）と Custom 分岐の最小例は、
同じディレクトリの workflows.py にあります（`uv run python step_04_multi_agent/workflows.py`）。
"""

from __future__ import annotations

import os

from google.adk.agents import Agent

MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")

billing_agent = Agent(
    name="billing_agent",
    model=MODEL,
    description="料金・請求・支払い・返金に関する問い合わせに答える担当。",
    instruction=(
        "あなたは請求担当です。料金・支払い方法・返金について丁寧に説明してください。"
        "担当外の話題が来たら、その旨を伝えて受付に戻してください。"
    ),
)

tech_agent = Agent(
    name="tech_agent",
    model=MODEL,
    description="製品の不具合・エラー・設定など、技術的なトラブルシューティング担当。",
    instruction=(
        "あなたは技術サポート担当です。不具合の切り分け手順を簡潔に案内してください。"
        "担当外の話題が来たら、その旨を伝えて受付に戻してください。"
    ),
)

general_agent = Agent(
    name="general_agent",
    model=MODEL,
    description="請求・技術以外の一般的な問い合わせや雑談に答える担当。",
    instruction="あなたは総合窓口です。一般的な問い合わせに簡潔に答えてください。",
)

# coordinator（受付）= root_agent。内容に応じて適切な担当へ転送します。
root_agent = Agent(
    name="help_desk",
    model=MODEL,
    description="問い合わせ窓口。内容に応じて適切な担当へ振り分ける受付。",
    instruction=(
        "あなたはヘルプデスクの受付です。ユーザーの問い合わせ内容を読み、最も適した"
        "担当へ転送してください。料金・支払いは billing_agent、技術的な不具合は"
        " tech_agent、それ以外は general_agent に任せます。"
        "簡単な挨拶や雑談には、自分で短く答えてもかまいません。"
    ),
    sub_agents=[billing_agent, tech_agent, general_agent],
)
