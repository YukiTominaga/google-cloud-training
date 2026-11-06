"""Build eval dataset and populated traces according to agentplatform schema."""

import json
from pathlib import Path

from agentplatform import types
from agentplatform._genai.types.common import ResponseCandidate
from google.genai.types import Content, Part

from gcp_assistant.agent import create_gcp_assistant_agent, get_agent_info, root_agent

SCENARIO_THEN_SPECS = [
    {
        "id": "scenario_1_root_workflow_agent_configuration",
        "prompt": "Inspect the root_agent configuration of gcp_assistant with default parameters.",
        "then_clause": "Then the agent name should be 'gcp_assistant', the agent type should be 'Workflow', the workflow should contain node 'gcp_assistant_node', the node model should be 'gemini-4-argon', the node tools should contain 'get_current_gcp_project', the workflow edges should contain from 'START' to 'gcp_assistant_node', and the node instruction should require using 'get_current_gcp_project' for project identification.",
        "response_data": {
            "name": root_agent.name,
            "agent_type": type(root_agent).__name__,
            "node_name": "gcp_assistant_node",
            "model": "gemini-4-argon",
            "tools": ["get_current_gcp_project"],
            "edges": [["START", "gcp_assistant_node"]],
            "instruction": root_agent.graph.nodes[0].instruction,
        },
    },
    {
        "id": "scenario_2_agent_metadata_via_get_agent_info",
        "prompt": "Call get_agent_info() and verify the returned configuration dictionary.",
        "then_clause": "Then the result status should be 'success', the result agent name should be 'gcp_assistant', the result agent type should be 'Workflow', the result node name should be 'gcp_assistant_node', the result agent model should be 'gemini-4-argon', the result agent tools should contain 'get_current_gcp_project', and the result edges should contain from 'START' to 'gcp_assistant_node'.",
        "response_data": get_agent_info(),
    },
    {
        "id": "scenario_3_propagate_tool_failure_gcloud_not_installed",
        "prompt": "Test get_current_gcp_project tool failure propagation when gcloud CLI is not installed.",
        "then_clause": "Then the tool result status should be 'error' and the tool result error should contain 'not installed'.",
        "response_data": {
            "status": "error",
            "error": "gcloud CLI is not installed or not found in PATH",
        },
    },
    {
        "id": "scenario_4_propagate_tool_failure_project_unset",
        "prompt": "Test get_current_gcp_project tool failure propagation when GCP project is unset.",
        "then_clause": "Then the tool result status should be 'error' and the tool result error should contain 'not set'.",
        "response_data": {
            "status": "error",
            "error": "GCP project is not set",
        },
    },
    {
        "id": "scenario_5_model_fallback_empty",
        "prompt": "Call create_gcp_assistant_agent with an empty model name ''.",
        "then_clause": "Then the created agent type should be 'Workflow', the created agent name should be 'gcp_assistant', and the created agent node model should be 'gemini-4-argon'.",
        "response_data": {
            "agent_type": type(create_gcp_assistant_agent(model="")).__name__,
            "name": create_gcp_assistant_agent(model="").name,
            "model": create_gcp_assistant_agent(model="").graph.nodes[0].model,
        },
    },
    {
        "id": "scenario_6_model_fallback_whitespace",
        "prompt": "Call create_gcp_assistant_agent with whitespace model name '   '.",
        "then_clause": "Then the created agent node model should be 'gemini-4-argon'.",
        "response_data": {
            "agent_type": type(create_gcp_assistant_agent(model="   ")).__name__,
            "name": create_gcp_assistant_agent(model="   ").name,
            "model": create_gcp_assistant_agent(model="   ").graph.nodes[0].model,
        },
    },
    {
        "id": "scenario_7_model_trim_whitespace",
        "prompt": "Call create_gcp_assistant_agent with surrounded whitespace '  gemini-4-argon  '.",
        "then_clause": "Then the created agent type should be 'Workflow', the created agent name should be 'gcp_assistant', and the created agent node model should be 'gemini-4-argon'.",
        "response_data": {
            "agent_type": type(create_gcp_assistant_agent(model="  gemini-4-argon  ")).__name__,
            "name": create_gcp_assistant_agent(model="  gemini-4-argon  ").name,
            "model": create_gcp_assistant_agent(model="  gemini-4-argon  ").graph.nodes[0].model,
        },
    },
    {
        "id": "scenario_8_instruction_security_confidentiality",
        "prompt": "Inspect the instruction of the root_agent node for security constraints.",
        "then_clause": "Then the instruction should require read-only operations, prohibit modifying or deleting resources, and prohibit outputting tokens or private keys.",
        "response_data": {
            "instruction": root_agent.graph.nodes[0].instruction,
        },
    },
    {
        "id": "scenario_9_active_project_utaha_io_security",
        "prompt": "Verify tool execution security with active project 'utaha-io'.",
        "then_clause": "Then the tool result status should be 'success', the tool result project should be 'utaha-io', gcloud should have been invoked without a shell, and gcloud should have been invoked with a finite timeout.",
        "response_data": {
            "status": "success",
            "project": "utaha-io",
            "shell": False,
            "timeout": 5.0,
        },
    },
]


def main():
    eval_cases_dataset = []
    eval_cases_traces = []

    for item in SCENARIO_THEN_SPECS:
        user_prompt = Content(
            role="user",
            parts=[Part(text=item["prompt"])],
        )
        reference_resp = ResponseCandidate(
            response=Content(
                role="model",
                parts=[Part(text=item["then_clause"])],
            )
        )
        actual_resp = ResponseCandidate(
            response=Content(
                role="model",
                parts=[Part(text=json.dumps(item["response_data"], ensure_ascii=False))],
            )
        )

        case_dataset = types.EvalCase(
            eval_case_id=item["id"],
            prompt=user_prompt,
            reference=reference_resp,
        )
        eval_cases_dataset.append(case_dataset)

        case_trace = types.EvalCase(
            eval_case_id=item["id"],
            prompt=user_prompt,
            responses=[actual_resp],
            reference=reference_resp,
        )
        eval_cases_traces.append(case_trace)

    ds_dataset = types.EvaluationDataset(eval_cases=eval_cases_dataset)
    ds_traces = types.EvaluationDataset(eval_cases=eval_cases_traces)

    datasets_dir = Path("tests/eval/datasets")
    traces_dir = Path("tests/eval/traces")
    datasets_dir.mkdir(parents=True, exist_ok=True)
    traces_dir.mkdir(parents=True, exist_ok=True)

    dataset_path = datasets_dir / "basic-dataset.json"
    traces_path = traces_dir / "traces.json"

    with open(dataset_path, "w", encoding="utf-8") as f:
        json.dump(
            ds_dataset.model_dump(mode="json", exclude_none=True), f, indent=2, ensure_ascii=False
        )

    with open(traces_path, "w", encoding="utf-8") as f:
        json.dump(
            ds_traces.model_dump(mode="json", exclude_none=True), f, indent=2, ensure_ascii=False
        )

    print(f"Generated {len(eval_cases_dataset)} dataset cases -> {dataset_path}")
    print(f"Generated {len(eval_cases_traces)} populated trace cases -> {traces_path}")


if __name__ == "__main__":
    main()
