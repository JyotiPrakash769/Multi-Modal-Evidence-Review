import csv
import os
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
CODE_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(CODE_DIR))

ROOT_DIR = CODE_DIR.parent
SAMPLE_CSV = ROOT_DIR / "dataset" / "sample_claims.csv"
PREDICTIONS_A = SCRIPT_DIR / "predictions_strategy_a.csv"
PREDICTIONS_B = SCRIPT_DIR / "predictions_strategy_b.csv"
REPORT_PATH = SCRIPT_DIR / "evaluation_report.md"

from main import process_csv
from evaluation.metrics import (
    compute_exact_match_accuracy,
    format_metrics,
    compare_strategies,
)
from pipeline.gemini_client import get_token_counts, reset_token_counts


def run_evaluation():
    if not os.environ.get("OPENROUTER_API_KEY", ""):
        from dotenv import load_dotenv
        load_dotenv(dotenv_path=CODE_DIR / ".env")
        if not os.environ.get("OPENROUTER_API_KEY", ""):
            print("ERROR: OPENROUTER_API_KEY not set")
            sys.exit(1)

    start_total = time.time()
    all_token_counts = {}

    reset_token_counts()
    print("=== Strategy A: openai/gpt-4o-mini ===")
    t0 = time.time()
    preds_a = process_csv(SAMPLE_CSV, PREDICTIONS_A, "openai/gpt-4o-mini")
    time_a = time.time() - t0
    all_token_counts["gpt_4o_mini"] = get_token_counts()

    reset_token_counts()
    print("\n=== Strategy B: openai/gpt-4o ===")
    t0 = time.time()
    preds_b = process_csv(SAMPLE_CSV, PREDICTIONS_B, "openai/gpt-4o")
    time_b = time.time() - t0
    all_token_counts["gpt_4o"] = get_token_counts()

    total_runtime = time.time() - start_total

    sample_rows = []
    with open(SAMPLE_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            sample_rows.append(row)

    expected = []
    for row in sample_rows:
        expected.append({
            "user_id": row["user_id"],
            "image_paths": row["image_paths"],
            "user_claim": row["user_claim"],
            "claim_object": row["claim_object"],
            "evidence_standard_met": row.get("evidence_standard_met", ""),
            "evidence_standard_met_reason": row.get("evidence_standard_met_reason", ""),
            "risk_flags": row.get("risk_flags", ""),
            "issue_type": row.get("issue_type", ""),
            "object_part": row.get("object_part", ""),
            "claim_status": row.get("claim_status", ""),
            "claim_status_justification": row.get("claim_status_justification", ""),
            "supporting_image_ids": row.get("supporting_image_ids", ""),
            "valid_image": row.get("valid_image", ""),
            "severity": row.get("severity", ""),
        })

    metrics_a = compute_exact_match_accuracy(expected, preds_a)
    metrics_b = compute_exact_match_accuracy(expected, preds_b)

    winner = "B" if (metrics_b.get("claim_status_accuracy", {}).get("rate", 0)
                     > metrics_a.get("claim_status_accuracy", {}).get("rate", 0)) else "A"
    winner_model = "openai/gpt-4o" if winner == "B" else "openai/gpt-4o-mini"

    total_images = sum(len(row.get("image_paths", "").split(";")) for row in expected)

    report = []
    report.append("# Evaluation Report\n")
    report.append(f"**Date:** {time.strftime('%Y-%m-%dT%H:%M:%S%z')}\n")
    report.append(f"**Total samples:** {len(expected)}\n")
    report.append(f"**Total images:** {total_images}\n")
    report.append(f"**Total runtime (both strategies):** {total_runtime:.1f}s\n\n")
    report.append("---\n")
    report.append(format_metrics(metrics_a).replace("## Metrics", "## Strategy A (gemini-2.5-flash-lite) Metrics"))
    report.append("---\n")
    report.append(format_metrics(metrics_b).replace("## Metrics", "## Strategy B (gemini-2.5-flash) Metrics"))
    report.append("---\n")
    report.append(compare_strategies(metrics_a, metrics_b))
    report.append(f"## Final Choice\n\n")
    report.append(f"**Strategy {winner}** (`{winner_model}`) "
                  f"was chosen for the final run on `dataset/claims.csv`.\n\n")
    report.append("---\n")
    report.append("## Operational Analysis\n\n")

    for label, key in [("Strategy A (gpt-4o-mini)", "gpt_4o_mini"),
                        ("Strategy B (gpt-4o)", "gpt_4o")]:
        tc = all_token_counts.get(key, {})
        report.append(f"### {label}\n")
        report.append(f"- **API calls:** {tc.get('calls', 0)}\n")
        report.append(f"- **Prompt tokens:** {tc.get('prompt', 0)}\n")
        report.append(f"- **Completion tokens:** {tc.get('completion', 0)}\n")
        report.append(f"- **Runtime:** {time_a if key == 'gpt_4o_mini' else time_b:.1f}s\n")
        report.append(f"- **Images processed:** {total_images}\n")
        report.append(f"- **Estimated cost (OpenRouter):** $0.00 (free credits)\n")
        report.append(f"- **Estimated cost (paid, for reference):** "
                      f"~${(tc.get('prompt',0) * 0.00015 + tc.get('completion',0) * 0.0006) / 1000:.4f}\n\n")

    report.append(f"### Final Run (claims.csv)\n")
    report.append(f"- **Claims to process:** 44\n")
    report.append(f"- **Estimated API calls:** 44\n")
    report.append(f"- **Estimated runtime:** ~{(time_a if winner == 'A' else time_b) * 44 / max(len(expected), 1):.0f}s\n")
    report.append(f"- **Estimated cost (OpenRouter):** ~$0.00\n\n")
    report.append("### Rate Limiting Strategy\n\n")
    report.append("- **Sequential processing:** Claims are processed one at a time with a 2-second delay between calls.\n")
    report.append("- **Retry logic:** Exponential backoff for 429 (rate limit) errors.\n")
    report.append("- **Max retries:** 3 per call for rate limits.\n")
    report.append("- **Model choice:** `openai/gpt-4o-mini` is preferred for the free tier "
                  "due to low cost per token and strong vision capabilities.\n")
    report.append("- **TPM/RPM considerations:** At 2s delay between calls, the system stays well under "
                  "OpenRouter rate limits. No batching needed at this scale.\n")

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.writelines(report)

    print(f"\nEvaluation report written to: {REPORT_PATH}")
    print(f"Strategy A predictions: {PREDICTIONS_A}")
    print(f"Strategy B predictions: {PREDICTIONS_B}")


if __name__ == "__main__":
    run_evaluation()
