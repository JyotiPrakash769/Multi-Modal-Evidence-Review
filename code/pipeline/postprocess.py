from .schema import (
    OUTPUT_COLUMNS,
    ALLOWED_CLAIM_STATUS,
    ALLOWED_ISSUE_TYPE,
    ALLOWED_OBJECT_PART_MAP,
    ALLOWED_RISK_FLAGS,
    ALLOWED_SEVERITY,
)


def postprocess(
    model_output: dict,
    claim_object: str,
    history_is_risky: bool,
    original_row: dict,
    image_descriptions: dict[str, str] | None = None,
    evidence_texts: list[str] | None = None,
) -> dict:
    result = dict(original_row)

    result["evidence_standard_met"] = _validate_bool(model_output, "evidence_standard_met")
    result["evidence_standard_met_reason"] = str(
        model_output.get("evidence_standard_met_reason", "")
    )
    result["issue_type"] = _validate_issue_type(model_output)
    result["object_part"] = _validate_object_part(model_output, claim_object)
    result["claim_status"] = _validate_claim_status(model_output)
    result["claim_status_justification"] = str(
        model_output.get("claim_status_justification", "")
    )
    result["severity"] = _validate_severity(model_output)
    result["valid_image"] = _validate_bool(model_output, "valid_image")

    result["risk_flags"] = _build_risk_flags(model_output, history_is_risky)
    result["supporting_image_ids"] = _build_supporting_ids(model_output)

    # Intelligent defaults for fields often missed by local models
    if image_descriptions:
        valid_descs = {k: v for k, v in image_descriptions.items()
                       if v and "[Description failed]" not in v and "[Image not found]" not in v}
        if valid_descs:
            if result["valid_image"] == "false":
                result["valid_image"] = "true"
            if result["supporting_image_ids"] == "none":
                result["supporting_image_ids"] = ";".join(sorted(valid_descs.keys()))
            if result["evidence_standard_met"] == "false":
                result["evidence_standard_met"] = "true"
                result["evidence_standard_met_reason"] = f"{len(valid_descs)} valid images provided"
        if not result.get("claim_status_justification"):
            status = result.get("claim_status", "unknown")
            part = result.get("object_part", claim_object)
            result["claim_status_justification"] = f"Claim {status} for {part} damage."

    return result


def _validate_bool(model_output: dict, key: str) -> str:
    val = model_output.get(key)
    if val is True or str(val).lower() == "true":
        return "true"
    return "false"


def _validate_claim_status(model_output: dict) -> str:
    val = str(model_output.get("claim_status", "")).lower().strip()
    if val in ALLOWED_CLAIM_STATUS:
        return val
    return "not_enough_information"


def _validate_issue_type(model_output: dict) -> str:
    val = str(model_output.get("issue_type", "")).lower().strip()
    if val in ALLOWED_ISSUE_TYPE:
        return val
    return "unknown"


def _validate_object_part(model_output: dict, claim_object: str) -> str:
    val = str(model_output.get("object_part", "")).lower().strip().replace(" ", "_")
    allowed = ALLOWED_OBJECT_PART_MAP.get(claim_object, ["unknown"])
    if val in allowed:
        return val
    return "unknown"


def _validate_severity(model_output: dict) -> str:
    val = str(model_output.get("severity", "")).lower().strip()
    if val in ALLOWED_SEVERITY:
        return val
    return "unknown"


def _build_risk_flags(model_output: dict, history_is_risky: bool) -> str:
    model_flags = model_output.get("model_risk_flags", [])
    if not isinstance(model_flags, list):
        model_flags = []

    flags = set()
    for f in model_flags:
        f_clean = str(f).lower().strip().replace(" ", "_")
        if f_clean in ALLOWED_RISK_FLAGS:
            flags.add(f_clean)

    if history_is_risky:
        flags.add("user_history_risk")

    if flags:
        flags.add("manual_review_required")
        return ";".join(sorted(flags))

    return "none"


def _build_supporting_ids(model_output: dict) -> str:
    ids = model_output.get("supporting_image_ids", [])
    if isinstance(ids, str):
        ids = [ids]
    if not isinstance(ids, list):
        ids = []
    ids = [str(i).strip() for i in ids if str(i).strip()]
    if not ids:
        return "none"
    return ";".join(ids)
