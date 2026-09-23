"""step_02_agent_with_tools — ツールを使うエージェント。

このサンプルでは 2 種類のツールを扱います。

A. カスタム Function Tool（自作の Python 関数）
   - `tools=[my_func]` のように **素の関数を渡すだけ**で、ADK が自動的に
     FunctionTool としてラップします。
   - 関数の **docstring と型ヒントがそのまま LLM に渡され**、「いつ・どの引数で
     このツールを呼ぶか」の判断材料になります。docstring は LLM 向けの仕様書だと
     考えて、引数 (Args) と戻り値 (Returns) を明確に書きます。
   - 戻り値は dict が扱いやすく、`status` を入れておくと成否を LLM が判断しやすく
     なります。引数を変更せず新しい dict を返す（イミュータブル）実装にします。

B. 組み込みツール google_search（Gemini が内部実行する検索）
   - `google_search` は「Gemini モデルが内部で実行する組み込みツール」です。
   - 制約: **組み込みツールは、同一エージェント内で他のツールと併用できません。**
   - そのため定石として、google_search だけを持つ専用エージェントを作り、それを
     `AgentTool` で包んで親エージェントの 1 ツールとして渡します。こうすると
     「親はカスタムツール + 検索エージェント」という構成になり、制約を回避できます。
     （補足: `GoogleSearchTool(bypass_multi_tools_limit=True)` を使うと ADK が
     自動で AgentTool ラップを行いますが、ここでは仕組みが見える明示的な方法を採ります。）

対話方法は README.md を参照してください。
"""

from __future__ import annotations

import os

from google.adk.agents import Agent
from google.adk.tools import AgentTool, google_search

MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")

# デモ用の固定為替レート（1 単位あたりの USD 換算値）。
# 実運用では外部 API を呼びますが、サンプルでは決定的な静的データで代替します。
_USD_PER_UNIT = {
    "USD": 1.0,
    "JPY": 0.0064,
    "EUR": 1.08,
    "GBP": 1.27,
}


def convert_currency(amount: float, from_code: str, to_code: str) -> dict:
    """通貨を換算します（デモ用の固定レート）。

    Args:
        amount: 換算したい金額。
        from_code: 換算元の通貨コード（例: "USD", "JPY", "EUR", "GBP"）。
        to_code: 換算先の通貨コード（例: "JPY"）。

    Returns:
        status と、成功時は converted（換算後の金額）・to_code・rate（適用レート）、
        失敗時は error_message を含む dict。
    """
    src = from_code.strip().upper()
    dst = to_code.strip().upper()
    if src not in _USD_PER_UNIT or dst not in _USD_PER_UNIT:
        return {
            "status": "error",
            "error_message": (
                f"未対応の通貨コードです: {from_code} / {to_code}。"
                f" 対応コード: {', '.join(sorted(_USD_PER_UNIT))}"
            ),
        }
    rate = _USD_PER_UNIT[src] / _USD_PER_UNIT[dst]
    return {
        "status": "success",
        "converted": round(amount * rate, 2),
        "to_code": dst,
        "rate": round(rate, 6),
    }


def list_supported_currencies() -> dict:
    """通貨換算ツールが対応している通貨コードの一覧を返します。

    Returns:
        status と supported（対応する通貨コードのリスト）を含む dict。
    """
    return {"status": "success", "supported": sorted(_USD_PER_UNIT)}


# google_search だけを持つ専用エージェント。
# 組み込みツールを「他ツールと併用しない」状態に隔離するための器です。
search_agent = Agent(
    name="web_search_assistant",
    model=MODEL,
    description="Google 検索で最新情報を調べて答えるアシスタント。",
    instruction=(
        "ユーザーの質問に答えるため google_search で最新情報を検索し、"
        "出典に基づいて簡潔に回答してください。"
    ),
    tools=[google_search],
)

# 親エージェント: カスタムツール + 検索エージェント (AgentTool でラップ)。
root_agent = Agent(
    name="tool_using_agent",
    model=MODEL,
    description="通貨換算と Web 検索ができるアシスタント。",
    instruction=(
        "あなたは通貨換算と調べ物を手伝う日本語アシスタントです。"
        "通貨の換算や対応通貨の確認には convert_currency / list_supported_currencies を"
        "使います。最新の出来事や一般的な調べ物には web_search_assistant ツールを使います。"
        "ツールがエラー (status=error) を返したら、その内容をユーザーにわかりやすく伝えてください。"
    ),
    tools=[
        convert_currency,
        list_supported_currencies,
        # AgentTool: 別エージェントを「呼び出して結果を受け取る」ツールにする。
        # （step_04_multi_agent で学ぶ「転送 (transfer)」とは異なり、制御は親に戻ります。）
        AgentTool(agent=search_agent),
    ],
)
