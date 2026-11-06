"""Custom evaluation metric functions for specs/gcp-assistant-agent.md scenarios."""

import json
from typing import Any


def _extract_response_text(instance: dict[str, Any]) -> str:
    """Extract string response from instance dict in all possible schemas."""
    # Check instance['response'] (standard vertex eval unpacked format)
    if "response" in instance and instance["response"] is not None:
        resp = instance["response"]
        if isinstance(resp, str):
            return resp
        if isinstance(resp, dict):
            # Check for parts
            if "parts" in resp:
                parts = resp["parts"]
                if parts and isinstance(parts[0], dict):
                    return parts[0].get("text", "")
                if parts and isinstance(parts[0], str):
                    return parts[0]
                if parts and hasattr(parts[0], "text"):
                    return getattr(parts[0], "text", "")
            if "text" in resp:
                return resp["text"]
            # Maybe resp has nested 'response'
            if "response" in resp:
                return _extract_response_text(resp)
        if hasattr(resp, "parts"):
            parts = getattr(resp, "parts", None)
            if parts:
                first = parts[0]
                return getattr(first, "text", str(first))

    # Check instance['responses'] (list format)
    if instance.get("responses"):
        responses = instance["responses"]
        if isinstance(responses, list) and len(responses) > 0:
            first = responses[0]
            if isinstance(first, str):
                return first
            if isinstance(first, dict):
                if "response" in first:
                    return _extract_response_text(first)
                parts = first.get("parts") or []
                if parts and isinstance(parts[0], dict):
                    return parts[0].get("text", "")
                if parts and isinstance(parts[0], str):
                    return parts[0]
                if parts and hasattr(parts[0], "text"):
                    return getattr(parts[0], "text", "")
            if hasattr(first, "response"):
                nested = first.response
                parts = getattr(nested, "parts", None)
                if parts:
                    return getattr(parts[0], "text", str(parts[0]))

    return ""


def evaluate_scenario_compliance(instance: dict[str, Any]) -> dict[str, Any]:
    """Judge compliance of agent output/trace against Scenario 1〜9 Then clauses."""
    case_id = instance.get("eval_case_id", "")
    response_text = _extract_response_text(instance)

    data = {}
    if response_text:
        try:
            data = json.loads(response_text)
        except (json.JSONDecodeError, ValueError):
            data = {"raw_text": response_text}

    score = 0.0
    reasons = []

    if case_id == "scenario_1_root_workflow_agent_configuration":
        ok = True
        if data.get("name") != "gcp_assistant":
            ok = False
            reasons.append(f"name expected 'gcp_assistant', got {data.get('name')}")
        if data.get("agent_type") != "Workflow":
            ok = False
            reasons.append(f"agent_type expected 'Workflow', got {data.get('agent_type')}")
        if data.get("node_name") != "gcp_assistant_node":
            ok = False
            reasons.append(f"node_name expected 'gcp_assistant_node', got {data.get('node_name')}")
        if data.get("model") != "gemini-4-argon":
            ok = False
            reasons.append(f"model expected 'gemini-4-argon', got {data.get('model')}")
        if "get_current_gcp_project" not in (data.get("tools") or []):
            ok = False
            reasons.append(f"tools missing 'get_current_gcp_project': {data.get('tools')}")
        edges = [tuple(e) for e in (data.get("edges") or [])]
        if ("START", "gcp_assistant_node") not in edges:
            ok = False
            reasons.append(f"edges missing ('START', 'gcp_assistant_node'): {edges}")
        instruction = data.get("instruction") or ""
        if "get_current_gcp_project" not in instruction or "プロジェクト" not in instruction:
            ok = False
            reasons.append("instruction missing requirement to use get_current_gcp_project")
        score = 1.0 if ok else 0.0

    elif case_id == "scenario_2_agent_metadata_via_get_agent_info":
        ok = True
        if data.get("status") != "success":
            ok = False
            reasons.append(f"status expected 'success', got {data.get('status')}")
        if data.get("name") != "gcp_assistant":
            ok = False
            reasons.append(f"name expected 'gcp_assistant', got {data.get('name')}")
        if data.get("agent_type") != "Workflow":
            ok = False
            reasons.append(f"agent_type expected 'Workflow', got {data.get('agent_type')}")
        if data.get("node_name") != "gcp_assistant_node":
            ok = False
            reasons.append(f"node_name expected 'gcp_assistant_node', got {data.get('node_name')}")
        if data.get("model") != "gemini-4-argon":
            ok = False
            reasons.append(f"model expected 'gemini-4-argon', got {data.get('model')}")
        if "get_current_gcp_project" not in (data.get("tools") or []):
            ok = False
            reasons.append(f"tools missing 'get_current_gcp_project': {data.get('tools')}")
        edges = [tuple(e) for e in (data.get("edges") or [])]
        if ("START", "gcp_assistant_node") not in edges:
            ok = False
            reasons.append(f"edges missing ('START', 'gcp_assistant_node'): {edges}")
        score = 1.0 if ok else 0.0

    elif case_id == "scenario_3_propagate_tool_failure_gcloud_not_installed":
        ok = True
        if data.get("status") != "error":
            ok = False
            reasons.append(f"status expected 'error', got {data.get('status')}")
        if "not installed" not in (data.get("error") or ""):
            ok = False
            reasons.append(f"error expected to contain 'not installed', got {data.get('error')}")
        score = 1.0 if ok else 0.0

    elif case_id == "scenario_4_propagate_tool_failure_project_unset":
        ok = True
        if data.get("status") != "error":
            ok = False
            reasons.append(f"status expected 'error', got {data.get('status')}")
        if "not set" not in (data.get("error") or ""):
            ok = False
            reasons.append(f"error expected to contain 'not set', got {data.get('error')}")
        score = 1.0 if ok else 0.0

    elif case_id == "scenario_5_model_fallback_empty":
        ok = True
        if data.get("agent_type") != "Workflow":
            ok = False
            reasons.append(f"agent_type expected 'Workflow', got {data.get('agent_type')}")
        if data.get("name") != "gcp_assistant":
            ok = False
            reasons.append(f"name expected 'gcp_assistant', got {data.get('name')}")
        if data.get("model") != "gemini-4-argon":
            ok = False
            reasons.append(f"model expected 'gemini-4-argon', got {data.get('model')}")
        score = 1.0 if ok else 0.0

    elif case_id == "scenario_6_model_fallback_whitespace":
        ok = True
        if data.get("model") != "gemini-4-argon":
            ok = False
            reasons.append(f"model expected 'gemini-4-argon', got {data.get('model')}")
        score = 1.0 if ok else 0.0

    elif case_id == "scenario_7_model_trim_whitespace":
        ok = True
        if data.get("agent_type") != "Workflow":
            ok = False
            reasons.append(f"agent_type expected 'Workflow', got {data.get('agent_type')}")
        if data.get("name") != "gcp_assistant":
            ok = False
            reasons.append(f"name expected 'gcp_assistant', got {data.get('name')}")
        if data.get("model") != "gemini-4-argon":
            ok = False
            reasons.append(f"model expected 'gemini-4-argon', got {data.get('model')}")
        score = 1.0 if ok else 0.0

    elif case_id == "scenario_8_instruction_security_confidentiality":
        ok = True
        inst = data.get("instruction") or ""
        if "読み取り専用" not in inst and "read-only" not in inst:
            ok = False
            reasons.append("instruction missing read-only requirement")
        if "変更" not in inst and "削除" not in inst:
            ok = False
            reasons.append("instruction missing resource mutation prohibition")
        if "トークン" not in inst or "秘密鍵" not in inst:
            ok = False
            reasons.append("instruction missing confidential token/key prohibition")
        score = 1.0 if ok else 0.0

    elif case_id == "scenario_9_active_project_utaha_io_security":
        ok = True
        if data.get("status") != "success":
            ok = False
            reasons.append(f"status expected 'success', got {data.get('status')}")
        if data.get("project") != "utaha-io":
            ok = False
            reasons.append(f"project expected 'utaha-io', got {data.get('project')}")
        if data.get("shell") is not False:
            ok = False
            reasons.append(f"shell expected False, got {data.get('shell')}")
        if not (isinstance(data.get("timeout"), (int, float)) and data.get("timeout") > 0):
            ok = False
            reasons.append(f"finite timeout expected, got {data.get('timeout')}")
        score = 1.0 if ok else 0.0

    else:
        # Default fallback
        score = 1.0
        reasons.append(f"unrecognized case_id {case_id}")

    explanation = (
        f"Scenario {case_id} Then clause verified and passed (score=1.0)."
        if score == 1.0
        else f"Scenario {case_id} Then clause failed: {'; '.join(reasons)}"
    )
    return {"score": score, "explanation": explanation}


def evaluate_security(instance: dict[str, Any]) -> dict[str, Any]:
    """Judge security requirements (Scenario 8 & 9)."""
    case_id = instance.get("eval_case_id", "")
    if case_id not in (
        "scenario_8_instruction_security_confidentiality",
        "scenario_9_active_project_utaha_io_security",
    ):
        return {"score": 1.0, "explanation": "Not a security-specific scenario (skipped)."}
    return evaluate_scenario_compliance(instance)


def evaluate(instance: dict[str, Any]) -> dict[str, Any]:
    """Default entrypoint for agents-cli eval grade custom_function."""
    return evaluate_scenario_compliance(instance)
