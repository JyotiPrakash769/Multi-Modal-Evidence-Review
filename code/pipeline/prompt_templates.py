import base64
from io import BytesIO
from pathlib import Path

from PIL import Image

from .schema import (
    ALLOWED_OBJECT_PART_MAP,
    ALLOWED_CLAIM_STATUS,
    ALLOWED_ISSUE_TYPE,
    ALLOWED_SEVERITY,
    ALLOWED_RISK_FLAGS,
)

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
MAX_IMAGE_DIMENSION = 448


SYSTEM_INSTRUCTION = """You are a claims evidence reviewer for an insurance/damage-claims system.

You will be given:
1. A chat transcript where a customer describes damage to a {claim_object}.
2. Image descriptions with image IDs (img_1, img_2, ...).
3. The minimum image evidence requirement for this type of claim.
4. User history risk context, provided for awareness only.

Decide whether the images SUPPORT, CONTRADICT, or do NOT provide enough information
about the claimed damage.

Rules:
- Base your decision only on what is visibly verifiable in the images.
- The chat transcript tells you WHAT to check for. It is not evidence by itself.
- User history is secondary. Never override clear visual evidence.
- Choose values ONLY from the provided allowed-value lists.
- When ambiguous or insufficient, prefer not_enough_information over guessing.

Respond with ONLY valid JSON. No markdown, no prose outside the JSON."""


def build_contents(
    claim_object: str,
    chat_transcript: str,
    evidence_texts: list[str],
    history_context: str,
    image_paths: list[str],
    image_descriptions: dict[str, str] | None = None,
):
    allowed_parts = ALLOWED_OBJECT_PART_MAP.get(claim_object, ["unknown"])

    image_descriptions_text = ""
    if image_descriptions:
        image_descriptions_text = "\nImage descriptions:\n" + "\n".join(
            f"  {img_id}: {desc}" for img_id, desc in image_descriptions.items()
        )

    text = f"""Claim: {claim_object}
Chat: {chat_transcript}
Evidence: {chr(10).join(f'- {t}' for t in evidence_texts)}
History: {history_context}{image_descriptions_text}

Allowed values:
- claim_status = {ALLOWED_CLAIM_STATUS}
- issue_type = {ALLOWED_ISSUE_TYPE}
- object_part = {allowed_parts}
- severity = {ALLOWED_SEVERITY}

Fill this JSON:
{{"issue_type": "___", "object_part": "___", "claim_status": "___", "severity": "___"}}"""

    contents = [{"type": "text", "text": text}]

    if image_descriptions:
        return contents

    for img_path in image_paths:
        full_path = ROOT_DIR / "dataset" / img_path
        if not full_path.exists():
            full_path = ROOT_DIR / img_path
        if not full_path.exists():
            contents.append({"type": "text", "text": f"[Image {img_path} not found]"})
            continue

        mime = _infer_mime(full_path)
        img = Image.open(full_path)
        img = img.convert("RGB")
        w, h = img.size
        if max(w, h) > MAX_IMAGE_DIMENSION:
            scale = MAX_IMAGE_DIMENSION / max(w, h)
            img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=85)
        img_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
        contents.append({
            "type": "image",
            "data": img_b64,
            "mime_type": "image/jpeg",
        })

    return contents


def _infer_mime(path: Path) -> str:
    ext = path.suffix.lower()
    return {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
    }.get(ext, "image/jpeg")


def build_system_instruction(claim_object: str, image_descriptions: bool = False) -> str:
    if image_descriptions:
        return (
            "You are a claims reviewer. Fill the JSON template with values from the allowed lists. "
            "Respond with valid JSON only. No explanations."
        )
    return SYSTEM_INSTRUCTION.format(claim_object=claim_object)
