"""Run evaluation of gcp_assistant agent traces against specs Scenarios 1〜9."""

import json
import sys
from pathlib import Path

# Ensure this script directory is in sys.path
EVAL_DIR = Path(__file__).resolve().parent
if str(EVAL_DIR) not in sys.path:
    sys.path.insert(0, str(EVAL_DIR))

from judge_metric import evaluate_scenario_compliance, evaluate_security


def main():
    traces_path = EVAL_DIR / "traces" / "traces.json"
    if not traces_path.exists():
        print(f"Error: traces file not found at {traces_path}")
        return 1

    with open(traces_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    eval_cases = data.get("eval_cases", [])
    print(f"Loaded {len(eval_cases)} eval cases from {traces_path}")

    results = []
    scores = []
    security_scores = []

    print("\n" + "=" * 80)
    print(f"{'Case ID':<50} | {'Score':<6} | {'Status':<6}")
    print("-" * 80)

    for case in eval_cases:
        case_id = case.get("eval_case_id", "")
        comp_res = evaluate_scenario_compliance(case)
        sec_res = evaluate_security(case)

        score = comp_res.get("score", 0.0)
        sec_score = sec_res.get("score", 0.0)

        scores.append(score)
        security_scores.append(sec_score)

        status_str = "PASS" if score == 1.0 else "FAIL"
        print(f"{case_id:<50} | {score:<6.2f} | {status_str:<6}")

        results.append(
            {
                "eval_case_id": case_id,
                "score": score,
                "security_score": sec_score,
                "explanation": comp_res.get("explanation", ""),
                "prompt": case.get("prompt"),
                "reference": case.get("reference"),
            }
        )

    mean_score = sum(scores) / len(scores) if scores else 0.0
    sec_mean_score = sum(security_scores) / len(security_scores) if security_scores else 0.0

    print("=" * 80)
    print(
        f"Summary: scenario_then_compliance Mean Score = {mean_score:.4f} ({sum(1 for s in scores if s == 1.0)}/{len(scores)} passed)"
    )
    print(f"Summary: security_compliance Mean Score     = {sec_mean_score:.4f}")
    print("=" * 80 + "\n")

    output_dir = EVAL_DIR / "results"
    output_dir.mkdir(parents=True, exist_ok=True)
    out_file = output_dir / "eval_results.json"

    summary = {
        "metrics": {
            "scenario_then_compliance": {
                "mean_score": mean_score,
                "num_cases_total": len(eval_cases),
                "num_cases_passed": sum(1 for s in scores if s == 1.0),
                "num_cases_failed": sum(1 for s in scores if s < 1.0),
            },
            "security_compliance": {
                "mean_score": sec_mean_score,
                "num_cases_total": len(eval_cases),
                "num_cases_passed": sum(1 for s in security_scores if s == 1.0),
            },
        },
        "results": results,
    }

    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print(f"Evaluation results saved to {out_file}")
    return 0 if mean_score == 1.0 else 1


if __name__ == "__main__":
    sys.exit(main())
