"""Test that evaluation metrics and traces conform to specs and achieve 100% score."""

import json
from pathlib import Path

from tests.eval.judge_metric import evaluate_scenario_compliance, evaluate_security


def test_eval_dataset_and_traces_all_pass():
    traces_path = Path("tests/eval/traces/traces.json")
    assert traces_path.exists(), f"Traces file not found at {traces_path}"

    with open(traces_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    cases = data.get("eval_cases", [])
    assert len(cases) == 9, f"Expected 9 cases, got {len(cases)}"

    for case in cases:
        case_id = case.get("eval_case_id")
        comp_res = evaluate_scenario_compliance(case)
        assert comp_res["score"] == 1.0, (
            f"Case {case_id} failed compliance: {comp_res.get('explanation')}"
        )

        sec_res = evaluate_security(case)
        assert sec_res["score"] == 1.0, (
            f"Case {case_id} failed security check: {sec_res.get('explanation')}"
        )
