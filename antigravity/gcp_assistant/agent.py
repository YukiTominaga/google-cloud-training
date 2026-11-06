"""gcp_assistant の ADK エージェント本体定義。"""

from typing import Any

from google.adk.agents import LlmAgent
from google.adk.workflow import Workflow

from .tools import get_current_gcp_project

DEFAULT_MODEL: str = "gemini-4-argon"

INSTRUCTION: str = (
    "あなたは Google Cloud 環境の調査・支援を行うアシスタントです。\n"
    "以下のセキュリティおよび運用原則を厳格に遵守してください：\n"
    "1. プロジェクト特定: GCP プロジェクト ID を確認・特定する際は、推測を行わず必ず登録された "
    "get_current_gcp_project ツールを使用すること。\n"
    "2. 読み取り専用の原則: リソースの調査・確認など読み取り専用（read-only）の操作のみを行い、"
    "リソースの作成・変更・削除等の変更系操作は一切行わないこと。\n"
    "3. 機密情報の秘匿: アクセストークン、ID トークン、サービスアカウント秘密鍵、API キー等の"
    "機密情報を会話ログや出力に含めないこと。"
)


def create_gcp_assistant_agent(model: str | None = None) -> Workflow:
    """ADK 2.0 Graph API (Workflow) による gcp_assistant インスタンスを生成する。

    Args:
        model: 使用するモデル名。None、空文字、空白文字のみの場合は既定モデルにフォールバックする。

    Returns:
        設定済みの Workflow インスタンス。
    """
    if model is not None and model.strip():
        effective_model = model.strip()
    else:
        effective_model = DEFAULT_MODEL

    llm_node = LlmAgent(
        name="gcp_assistant_node",
        model=effective_model,
        instruction=INSTRUCTION,
        tools=[get_current_gcp_project],
    )

    workflow = Workflow(
        name="gcp_assistant",
        edges=[("START", llm_node)],
    )
    return workflow


# ADK Web や外部ツールが参照する既定のエージェントインスタンス
root_agent: Workflow = create_gcp_assistant_agent()


def get_agent_info() -> dict[str, Any]:
    """エージェントの構成情報辞書を取得する。

    Returns:
        成功時は構成情報を含む dict、失敗時はエラー情報を含む dict。
    """
    try:
        node = next((n for n in root_agent.graph.nodes if n.name == "gcp_assistant_node"), None)
        if node is None:
            return {"status": "error", "error": "Node 'gcp_assistant_node' not found"}

        model = getattr(node, "model", DEFAULT_MODEL)
        tool_names = [getattr(t, "__name__", str(t)) for t in getattr(node, "tools", [])]
        instruction = getattr(node, "instruction", INSTRUCTION)

        edges = []
        for edge in root_agent.graph.edges:
            from_name = edge.from_node.name
            if from_name == "__START__":
                from_name = "START"
            edges.append((from_name, edge.to_node.name))

        return {
            "status": "success",
            "name": root_agent.name,
            "agent_type": type(root_agent).__name__,
            "node_name": "gcp_assistant_node",
            "model": model,
            "tools": tool_names,
            "edges": edges,
            "instruction": instruction,
        }
    except (AttributeError, KeyError, IndexError, TypeError, ValueError, RuntimeError) as e:
        return {"status": "error", "error": str(e)}
