def compute_exact_match_accuracy(expected_list: list[dict], predicted_list: list[dict]) -> dict:
    total = len(expected_list)
    if total == 0:
        return {}

    def _match(e, p, key):
        return str(e.get(key, "")).strip().lower() == str(p.get(key, "")).strip().lower()

    fields = [
        "claim_status",
        "issue_type",
        "object_part",
        "severity",
        "evidence_standard_met",
        "valid_image",
    ]

    results = {}
    for field in fields:
        correct = sum(1 for e, p in zip(expected_list, predicted_list) if _match(e, p, field))
        results[f"{field}_accuracy"] = {
            "correct": correct,
            "total": total,
            "rate": round(correct / total, 3) if total else 0,
        }

    risk_scores = []
    supp_scores = []
    for e, p in zip(expected_list, predicted_list):
        risk_scores.append(
            _jaccard(
                _parse_set(e.get("risk_flags", "")),
                _parse_set(p.get("risk_flags", "")),
            )
        )
        supp_scores.append(
            _jaccard(
                _parse_set(e.get("supporting_image_ids", "")),
                _parse_set(p.get("supporting_image_ids", "")),
            )
        )

    results["risk_flags_jaccard"] = {
        "mean": round(sum(risk_scores) / len(risk_scores), 3) if risk_scores else 0,
    }
    results["supporting_image_ids_jaccard"] = {
        "mean": round(sum(supp_scores) / len(supp_scores), 3) if supp_scores else 0,
    }

    return results


def _parse_set(value: str) -> set[str]:
    if not value or str(value).strip().lower() == "none":
        return set()
    return {v.strip().lower() for v in str(value).split(";") if v.strip()}


def _jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 1.0
    union = a | b
    if not union:
        return 1.0
    return len(a & b) / len(union)


def format_metrics(metrics: dict) -> str:
    lines = ["## Metrics\n"]
    for key, val in metrics.items():
        if key.endswith("_accuracy"):
            lines.append(
                f"- **{key.replace('_accuracy', '').replace('_', ' ').title()}:** "
                f"{val['correct']}/{val['total']} ({val['rate']*100:.1f}%)"
            )
    for key in ["risk_flags_jaccard", "supporting_image_ids_jaccard"]:
        if key in metrics:
            lines.append(
                f"- **{key.replace('_', ' ').title()}:** "
                f"{metrics[key]['mean']:.3f}"
            )
    lines.append("")
    return "\n".join(lines)


def compare_strategies(metrics_a: dict, metrics_b: dict) -> str:
    lines = ["## Strategy Comparison\n"]
    lines.append("| Metric | Strategy A (flash-lite) | Strategy B (flash) | Winner |")
    lines.append("|--------|------------------------|---------------------|--------|")

    for key in sorted(set(list(metrics_a.keys()) + list(metrics_b.keys()))):
        if key.endswith("_accuracy"):
            a_val = f"{metrics_a[key]['rate']*100:.1f}%" if key in metrics_a else "N/A"
            b_val = f"{metrics_b[key]['rate']*100:.1f}%" if key in metrics_b else "N/A"
            a_rate = metrics_a[key]['rate'] if key in metrics_a else 0
            b_rate = metrics_b[key]['rate'] if key in metrics_b else 0
            if a_rate > b_rate:
                winner = "A"
            elif b_rate > a_rate:
                winner = "B"
            else:
                winner = "tie"
            label = key.replace("_accuracy", "").replace("_", " ").title()
            lines.append(f"| {label} | {a_val} | {b_val} | {winner} |")
        elif key in ("risk_flags_jaccard", "supporting_image_ids_jaccard"):
            a_val = f"{metrics_a[key]['mean']:.3f}" if key in metrics_a else "N/A"
            b_val = f"{metrics_b[key]['mean']:.3f}" if key in metrics_b else "N/A"
            a_rate = metrics_a[key]['mean'] if key in metrics_a else 0
            b_rate = metrics_b[key]['mean'] if key in metrics_b else 0
            if a_rate > b_rate:
                winner = "A"
            elif b_rate > a_rate:
                winner = "B"
            else:
                winner = "tie"
            label = key.replace("_", " ").title()
            lines.append(f"| {label} | {a_val} | {b_val} | {winner} |")

    lines.append("")
    return "\n".join(lines)
