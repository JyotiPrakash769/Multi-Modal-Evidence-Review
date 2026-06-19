OUTPUT_COLUMNS = [
    "user_id",
    "image_paths",
    "user_claim",
    "claim_object",
    "evidence_standard_met",
    "evidence_standard_met_reason",
    "risk_flags",
    "issue_type",
    "object_part",
    "claim_status",
    "claim_status_justification",
    "supporting_image_ids",
    "valid_image",
    "severity",
]

ALLOWED_CLAIM_STATUS = [
    "supported",
    "contradicted",
    "not_enough_information",
]

ALLOWED_ISSUE_TYPE = [
    "dent",
    "scratch",
    "crack",
    "glass_shatter",
    "broken_part",
    "missing_part",
    "torn_packaging",
    "crushed_packaging",
    "water_damage",
    "stain",
    "none",
    "unknown",
]

ALLOWED_OBJECT_PART_CAR = [
    "front_bumper",
    "rear_bumper",
    "door",
    "hood",
    "windshield",
    "side_mirror",
    "headlight",
    "taillight",
    "fender",
    "quarter_panel",
    "body",
    "unknown",
]

ALLOWED_OBJECT_PART_LAPTOP = [
    "screen",
    "keyboard",
    "trackpad",
    "hinge",
    "lid",
    "corner",
    "port",
    "base",
    "body",
    "unknown",
]

ALLOWED_OBJECT_PART_PACKAGE = [
    "box",
    "package_corner",
    "package_side",
    "seal",
    "label",
    "contents",
    "item",
    "unknown",
]

ALLOWED_OBJECT_PART_MAP = {
    "car": ALLOWED_OBJECT_PART_CAR,
    "laptop": ALLOWED_OBJECT_PART_LAPTOP,
    "package": ALLOWED_OBJECT_PART_PACKAGE,
}

ALLOWED_RISK_FLAGS = [
    "blurry_image",
    "cropped_or_obstructed",
    "low_light_or_glare",
    "wrong_angle",
    "wrong_object",
    "wrong_object_part",
    "damage_not_visible",
    "claim_mismatch",
    "possible_manipulation",
    "non_original_image",
    "text_instruction_present",
    "user_history_risk",
    "manual_review_required",
]

ALLOWED_SEVERITY = [
    "none",
    "low",
    "medium",
    "high",
    "unknown",
]
