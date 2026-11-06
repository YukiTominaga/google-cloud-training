"""specs/gcp-assistant-agent.md の Scenario 1〜9 に対する pytest-bdd ステップ定義。"""

import subprocess
from typing import Any

from pytest_bdd import given, parsers, scenarios, then, when

from gcp_assistant.agent import create_gcp_assistant_agent, get_agent_info, root_agent

scenarios("../features/gcp_assistant_agent.feature")


# ---------------------------------------------------------------------------
# Given ステップ
# ---------------------------------------------------------------------------


@given("the gcp_assistant agent module is loaded")
def agent_module_loaded(bdd_context: dict[str, Any]) -> None:
    """gcp_assistant エージェントモジュールが正常にインポートされていることを確認する。"""
    assert root_agent is not None
    bdd_context["agent"] = root_agent


@given("gcloud CLI is installed")
def gcloud_installed() -> None:
    """gcloud CLI がインストールされているマーカーステップ。"""


@given("gcloud CLI is not installed")
def mock_gcloud_not_installed(monkeypatch: Any) -> None:
    """gcloud CLI が未インストール（FileNotFoundError）の挙動を模擬する。"""

    def fake_run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        raise FileNotFoundError("[Errno 2] No such file or directory: 'gcloud'")

    monkeypatch.setattr(subprocess, "run", fake_run)


@given(parsers.re(r'gcloud command succeeds with output "(?P<output>.*)"'))
def mock_gcloud_output(monkeypatch: Any, output: str) -> None:
    """gcloud コマンドが終了コード 0 で指定出力を返す挙動を模擬する。"""

    def fake_run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=args[0] if args else kwargs.get("args"),
            returncode=0,
            stdout=f"{output}\n",
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)


@given(parsers.re(r'a model name is specified as "(?P<model_name>.*)"'))
def set_model_name_arg(bdd_context: dict[str, Any], model_name: str) -> None:
    """テスト対象のモデル引数を保持する。"""
    bdd_context["model_arg"] = model_name


@given("the root_agent node instruction is inspected")
def inspect_root_agent_instruction(bdd_context: dict[str, Any]) -> None:
    """root_agent 内の gcp_assistant_node のシステム指示を抽出する。"""
    node = next((n for n in root_agent.graph.nodes if n.name == "gcp_assistant_node"), None)
    assert node is not None, "Node 'gcp_assistant_node' not found in root_agent"
    bdd_context["instruction"] = getattr(node, "instruction", "")


@given(
    parsers.parse('gcloud config has active project "{project_id}" and calls are recorded'),
    target_fixture="recorded_calls",
)
def mock_gcloud_recorded(
    monkeypatch: Any, bdd_context: dict[str, Any], project_id: str
) -> list[dict[str, Any]]:
    """呼び出し引数を記録しつつアクティブプロジェクトを返す gcloud を模擬する。"""
    calls: list[dict[str, Any]] = []

    def fake_run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append({"args": args, "kwargs": kwargs})
        return subprocess.CompletedProcess(
            args=args[0] if args else kwargs.get("args"),
            returncode=0,
            stdout=f"{project_id}\n",
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    bdd_context["recorded_calls"] = calls
    return calls


# ---------------------------------------------------------------------------
# When ステップ
# ---------------------------------------------------------------------------


@when("root_agent is inspected")
def inspect_root_agent(bdd_context: dict[str, Any]) -> None:
    """root_agent インスタンスを検証コンテキストに格納する。"""
    bdd_context["agent"] = root_agent


@when("get_agent_info is called")
def call_get_agent_info(bdd_context: dict[str, Any]) -> None:
    """get_agent_info 関数を呼び出して結果を格納する。"""
    info = get_agent_info()
    bdd_context["info"] = info
    bdd_context["result"] = info


@when("the agent invokes get_current_gcp_project tool")
def agent_invokes_tool(bdd_context: dict[str, Any]) -> None:
    """エージェントノードにバインドされた get_current_gcp_project ツールを実行する。"""
    node = next((n for n in root_agent.graph.nodes if n.name == "gcp_assistant_node"), None)
    assert node is not None, "Node 'gcp_assistant_node' not found in root_agent"
    tools = getattr(node, "tools", [])
    tool_fn = next(
        (t for t in tools if getattr(t, "__name__", "") == "get_current_gcp_project"), None
    )
    assert tool_fn is not None, "Tool 'get_current_gcp_project' not found on node"
    bdd_context["tool_result"] = tool_fn()


@when("create_gcp_assistant_agent is called with the model name")
def call_create_agent(bdd_context: dict[str, Any]) -> None:
    """指定されたモデル名引数で create_gcp_assistant_agent を呼び出す。"""
    model_name = bdd_context.get("model_arg")
    created = create_gcp_assistant_agent(model_name)
    bdd_context["created_agent"] = created


# ---------------------------------------------------------------------------
# Then ステップ
# ---------------------------------------------------------------------------


@then(parsers.parse('the agent name should be "{expected_name}"'))
def verify_agent_name(bdd_context: dict[str, Any], expected_name: str) -> None:
    """root_agent の名前を検証する。"""
    assert bdd_context["agent"].name == expected_name


@then(parsers.parse('the agent type should be "{expected_type}"'))
def verify_agent_type(bdd_context: dict[str, Any], expected_type: str) -> None:
    """root_agent のクラス型名を検証する。"""
    assert type(bdd_context["agent"]).__name__ == expected_type


@then(parsers.parse('the workflow should contain node "{node_name}"'))
def verify_workflow_contains_node(bdd_context: dict[str, Any], node_name: str) -> None:
    """Workflow グラフ内に指定ノードが存在することを検証する。"""
    agent = bdd_context["agent"]
    node = next((n for n in agent.graph.nodes if n.name == node_name), None)
    assert node is not None, f"Node {node_name} not found in workflow"
    bdd_context["node"] = node


@then(parsers.parse('the node model should be "{expected_model}"'))
def verify_node_model(bdd_context: dict[str, Any], expected_model: str) -> None:
    """ノードのモデル名を検証する。"""
    assert bdd_context["node"].model == expected_model


@then(parsers.parse('the node tools should contain "{expected_tool}"'))
def verify_node_tools(bdd_context: dict[str, Any], expected_tool: str) -> None:
    """ノードに指定ツールが登録されていることを検証する。"""
    tools = getattr(bdd_context["node"], "tools", [])
    tool_names = [getattr(t, "__name__", str(t)) for t in tools]
    assert expected_tool in tool_names


@then(parsers.parse('the workflow edges should contain from "{from_name}" to "{to_name}"'))
def verify_workflow_edges(bdd_context: dict[str, Any], from_name: str, to_name: str) -> None:
    """Workflow グラフのエッジ接続を検証する（ADK 2.0 の START / __START__ を許容）。"""
    agent = bdd_context["agent"]
    matches = [
        e
        for e in agent.graph.edges
        if (
            e.from_node.name == from_name
            or (from_name == "START" and e.from_node.name == "__START__")
        )
        and e.to_node.name == to_name
    ]
    assert matches, f"Edge ({from_name}, {to_name}) not found in workflow edges"


@then(
    parsers.parse(
        'the node instruction should require using "{expected_tool}" for project identification'
    )
)
def verify_node_instruction_tool(bdd_context: dict[str, Any], expected_tool: str) -> None:
    """システム指示にツールを用いたプロジェクト特定の要件が含まれていることを検証する。"""
    instruction = bdd_context["node"].instruction
    assert expected_tool in instruction
    assert "プロジェクト" in instruction


@then(parsers.parse('the result status should be "{expected_status}"'))
def verify_result_status(bdd_context: dict[str, Any], expected_status: str) -> None:
    """返却辞書の status を検証する。"""
    assert bdd_context["result"]["status"] == expected_status


@then(parsers.parse('the result agent name should be "{expected_name}"'))
def verify_result_agent_name(bdd_context: dict[str, Any], expected_name: str) -> None:
    """get_agent_info の返却エージェント名を検証する。"""
    assert bdd_context["info"]["name"] == expected_name


@then(parsers.parse('the result agent type should be "{expected_type}"'))
def verify_result_agent_type(bdd_context: dict[str, Any], expected_type: str) -> None:
    """get_agent_info の返却 agent_type を検証する。"""
    assert bdd_context["info"]["agent_type"] == expected_type


@then(parsers.parse('the result node name should be "{expected_node_name}"'))
def verify_result_node_name(bdd_context: dict[str, Any], expected_node_name: str) -> None:
    """get_agent_info の返却 node_name を検証する。"""
    assert bdd_context["info"]["node_name"] == expected_node_name


@then(parsers.parse('the result agent model should be "{expected_model}"'))
def verify_result_agent_model(bdd_context: dict[str, Any], expected_model: str) -> None:
    """get_agent_info の返却 model を検証する。"""
    assert bdd_context["info"]["model"] == expected_model


@then(parsers.parse('the result agent tools should contain "{expected_tool}"'))
def verify_result_agent_tools(bdd_context: dict[str, Any], expected_tool: str) -> None:
    """get_agent_info の返却 tools リストを検証する。"""
    assert expected_tool in bdd_context["info"]["tools"]


@then(parsers.parse('the result edges should contain from "{from_name}" to "{to_name}"'))
def verify_result_edges(bdd_context: dict[str, Any], from_name: str, to_name: str) -> None:
    """get_agent_info の返却 edges を検証する。"""
    edges = bdd_context["info"]["edges"]
    assert (from_name, to_name) in edges or (
        from_name == "START" and ("__START__", to_name) in edges
    )


@then(parsers.parse('the tool result status should be "{expected_status}"'))
def verify_tool_result_status(bdd_context: dict[str, Any], expected_status: str) -> None:
    """ツール呼び出し結果の status を検証する。"""
    assert bdd_context["tool_result"]["status"] == expected_status


@then(parsers.parse('the tool result error should contain "{expected_error}"'))
def verify_tool_result_error(bdd_context: dict[str, Any], expected_error: str) -> None:
    """ツール呼び出し結果のエラーメッセージを検証する。"""
    error = bdd_context["tool_result"].get("error", "")
    assert expected_error in error


@then(parsers.parse('the created agent type should be "{expected_type}"'))
def verify_created_agent_type(bdd_context: dict[str, Any], expected_type: str) -> None:
    """ファクトリ生成エージェントの型を検証する。"""
    assert type(bdd_context["created_agent"]).__name__ == expected_type


@then(parsers.parse('the created agent name should be "{expected_name}"'))
def verify_created_agent_name(bdd_context: dict[str, Any], expected_name: str) -> None:
    """ファクトリ生成エージェントの名前を検証する。"""
    assert bdd_context["created_agent"].name == expected_name


@then(parsers.parse('the created agent node model should be "{expected_model}"'))
def verify_created_agent_node_model(bdd_context: dict[str, Any], expected_model: str) -> None:
    """ファクトリ生成エージェントのノードモデル名を検証する。"""
    node = next(
        (n for n in bdd_context["created_agent"].graph.nodes if n.name == "gcp_assistant_node"),
        None,
    )
    assert node is not None, "Node 'gcp_assistant_node' not found in created agent"
    assert node.model == expected_model


@then("the instruction should require read-only operations")
def verify_instruction_read_only(bdd_context: dict[str, Any]) -> None:
    """システム指示が読み取り専用操作を要求していることを検証する。"""
    instruction = bdd_context["instruction"]
    assert "読み取り専用" in instruction or "read-only" in instruction.lower()


@then("the instruction should prohibit modifying or deleting resources")
def verify_instruction_prohibit_modifications(bdd_context: dict[str, Any]) -> None:
    """システム指示がリソースの作成・変更・削除を禁止していることを検証する。"""
    instruction = bdd_context["instruction"]
    assert "作成" in instruction or "変更" in instruction or "削除" in instruction
    assert "行わない" in instruction or "禁止" in instruction


@then("the instruction should prohibit outputting tokens or private keys")
def verify_instruction_prohibit_secrets(bdd_context: dict[str, Any]) -> None:
    """システム指示がトークンや秘密鍵等の機密情報出力を禁止していることを検証する。"""
    instruction = bdd_context["instruction"]
    assert "トークン" in instruction or "秘密鍵" in instruction or "API キー" in instruction
    assert "含めない" in instruction or "禁止" in instruction


@then(parsers.parse('the tool result project should be "{expected_project}"'))
def verify_tool_result_project(bdd_context: dict[str, Any], expected_project: str) -> None:
    """ツール呼び出し結果のアクティブプロジェクトを検証する。"""
    assert bdd_context["tool_result"].get("project") == expected_project


@then("gcloud should have been invoked without a shell")
def verify_no_shell(recorded_calls: list[dict[str, Any]]) -> None:
    """shell=True が使われておらず引数がリスト形式であることを検証する。"""
    assert recorded_calls, "No subprocess calls recorded"
    for call in recorded_calls:
        assert not call["kwargs"].get("shell", False)
        cmd = call["args"][0] if call["args"] else call["kwargs"].get("args")
        assert isinstance(cmd, list)


@then("gcloud should have been invoked with a finite timeout")
def verify_finite_timeout(recorded_calls: list[dict[str, Any]]) -> None:
    """有限の正のタイムアウトが指定されていることを検証する。"""
    assert recorded_calls, "No subprocess calls recorded"
    for call in recorded_calls:
        timeout = call["kwargs"].get("timeout")
        assert isinstance(timeout, (int, float)) and timeout > 0
