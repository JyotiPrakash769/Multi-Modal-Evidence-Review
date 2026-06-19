import base64
import json
import os
import re
import time
from io import BytesIO
from pathlib import Path

from dotenv import load_dotenv
from PIL import Image
import requests

_env_path = Path(__file__).resolve().parent.parent / ".env"
if _env_path.exists():
    load_dotenv(dotenv_path=_env_path)

PROVIDER = os.environ.get("PROVIDER", "gemini").lower()
_token_counts = {"prompt": 0, "completion": 0, "calls": 0}

_FALLBACK = {
    "evidence_standard_met": False,
    "evidence_standard_met_reason": "System error during processing",
    "issue_type": "unknown",
    "object_part": "unknown",
    "claim_status": "not_enough_information",
    "claim_status_justification": "The system encountered an error and could not analyze this claim.",
    "supporting_image_ids": [],
    "valid_image": False,
    "severity": "unknown",
    "model_risk_flags": ["manual_review_required"],
}


def get_token_counts() -> dict:
    return dict(_token_counts)


def reset_token_counts():
    _token_counts["prompt"] = 0
    _token_counts["completion"] = 0
    _token_counts["calls"] = 0


# --- Gemini-direct provider (uses google-genai SDK) ---

_gemini_client_instance = None


def _get_gemini_client():
    global _gemini_client_instance
    if _gemini_client_instance is not None:
        return _gemini_client_instance
    key = os.environ.get("GEMINI_API_KEY", "")
    if not key:
        return None
    from google import genai
    _gemini_client_instance = genai.Client(api_key=key)
    return _gemini_client_instance


def _call_gemini_direct(model_name, contents, sys_inst):
    from google.genai import types

    client = _get_gemini_client()
    if not client:
        print("ERROR: Set GEMINI_API_KEY in .env")
        return dict(_FALLBACK)

    prompt_parts = []
    for part in contents:
        if part.get("type") == "text":
            prompt_parts.append(types.Part.from_text(text=part["text"]))
        elif part.get("type") == "image":
            import base64
            img_bytes = base64.b64decode(part["data"])
            mime = part.get("mime_type", "image/jpeg")
            prompt_parts.append(types.Part.from_bytes(data=img_bytes, mime_type=mime))

    config = {
        "temperature": 0.1,
        "max_output_tokens": 8192,
        "response_mime_type": "application/json",
    }
    if sys_inst:
        config["system_instruction"] = sys_inst

    max_retries = 3
    for attempt in range(max_retries + 1):
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt_parts,
                config=types.GenerateContentConfig(**config),
            )

            if response.usage_metadata:
                _token_counts["prompt"] += (response.usage_metadata.prompt_token_count or 0)
                _token_counts["completion"] += (response.usage_metadata.candidates_token_count or 0)
            _token_counts["calls"] += 1

            raw = response.text.strip()
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)
            return json.loads(raw)

        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                if attempt < max_retries:
                    import re as _re
                    m = _re.search(r"retryDelay['\"]:\s*['\"]([\d.]+)s", err_str)
                    delay = float(m.group(1)) + 2 if m else 20 * (attempt + 1)
                    print(f"Rate limited (attempt {attempt+1}), waiting {delay:.0f}s...")
                    time.sleep(delay)
                    continue
            elif attempt < max_retries:
                wait = 10 * (attempt + 1)
                print(f"API error (attempt {attempt+1}), retrying in {wait}s: {err_str[:80]}")
                time.sleep(wait)
                continue
            return dict(_FALLBACK)

    return dict(_FALLBACK)


# --- OpenAI-compatible providers (OpenRouter, Groq, OpenAI) ---

_openai_client_instance = None


def _get_openai_client():
    global _openai_client_instance
    if _openai_client_instance is not None:
        return _openai_client_instance

    PROVIDER_CONFIG = {
        "openrouter": {
            "base_url": "https://openrouter.ai/api/v1",
            "env_key": "OPENROUTER_API_KEY",
        },
        "groq": {
            "base_url": "https://api.groq.com/openai/v1",
            "env_key": "GROQ_API_KEY",
        },
        "openai": {
            "base_url": "https://api.openai.com/v1",
            "env_key": "OPENAI_API_KEY",
        },
        "ollama": {
            "base_url": "http://localhost:11434/v1",
            "env_key": "",
        },
    }

    cfg = PROVIDER_CONFIG.get(PROVIDER)
    if not cfg:
        return None

    if cfg["env_key"]:
        key = os.environ.get(cfg["env_key"], "")
        if not key:
            return None
    else:
        key = "ollama-placeholder"

    from openai import OpenAI
    kwargs = {"base_url": cfg["base_url"], "api_key": key}
    if PROVIDER == "openrouter":
        kwargs["default_headers"] = {
            "HTTP-Referer": "https://github.com/interviewstreet/hackerrank-orchestrate-june26",
            "X-Title": "HackerRank Orchestrate",
        }
    _openai_client_instance = OpenAI(**kwargs)
    return _openai_client_instance


def _call_openai_compat(model_name, contents, sys_inst):
    client = _get_openai_client()
    if not client:
        return dict(_FALLBACK)

    messages = []
    if sys_inst:
        messages.append({"role": "system", "content": sys_inst})

    user_content = []
    for part in contents:
        if part.get("type") == "text":
            user_content.append({"type": "text", "text": part["text"]})
        elif part.get("type") == "image":
            img_b64 = part["data"]
            mime = part.get("mime_type", "image/jpeg")
            user_content.append({
                "type": "image_url",
                "image_url": {"url": f"data:{mime};base64,{img_b64}"},
            })

    messages.append({"role": "user", "content": user_content})

    max_retries = 3
    for attempt in range(max_retries + 1):
        try:
            kwargs = {
                "model": model_name,
                "messages": messages,
                "temperature": 0.1,
                "max_tokens": 8192,
            }
            if PROVIDER == "ollama":
                kwargs["extra_body"] = {"options": {"num_ctx": 4096}}
            response = client.chat.completions.create(**kwargs)

            if response.usage:
                _token_counts["prompt"] += (response.usage.prompt_tokens or 0)
                _token_counts["completion"] += (response.usage.completion_tokens or 0)
            _token_counts["calls"] += 1

            raw = response.choices[0].message.content.strip()
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)
            return json.loads(raw)

        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "rate" in err_str.lower() or "quota" in err_str.lower() or "402" in err_str:
                if attempt < max_retries:
                    wait = 15 * (attempt + 1)
                    print(f"Rate limited (attempt {attempt+1}), waiting {wait}s...")
                    time.sleep(wait)
                    continue
            elif attempt < max_retries:
                wait = 5 * (attempt + 1)
                print(f"API error (attempt {attempt+1}), retrying in {wait}s: {err_str[:80]}")
                time.sleep(wait)
                continue
            return dict(_FALLBACK)

    return dict(_FALLBACK)


# --- Image description (two-stage pipeline for local models) ---

_DESCRIPTION_PROMPT = (
    "Describe this image in 2-3 concise sentences. "
    "Mention the object type, its condition, and any visible damage, scratches, dents, cracks, or defects. "
    "If no damage is visible, state that the object appears undamaged."
)


def _resize_image_bytes(img_bytes: bytes, max_dim: int = 384) -> tuple[bytes, str]:
    img = Image.open(BytesIO(img_bytes))
    img = img.convert("RGB")
    w, h = img.size
    if max(w, h) > max_dim:
        scale = max_dim / max(w, h)
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue(), "image/jpeg"


def describe_images(image_paths: list[str], model_name: str = "moondream") -> dict[str, str]:
    """Describe each image using the VLM (chat completions endpoint), returning {image_id: description}."""
    from .prompt_templates import ROOT_DIR
    client = _get_openai_client()
    if not client:
        return {}

    descriptions = {}
    for img_rel in image_paths:
        full_path = ROOT_DIR / "dataset" / img_rel
        if not full_path.exists():
            full_path = ROOT_DIR / img_rel
        if not full_path.exists():
            descriptions[Path(img_rel).stem] = "[Image not found]"
            continue

        img_id = Path(img_rel).stem
        with open(full_path, "rb") as f:
            img_bytes = f.read()
        img_resized, mime = _resize_image_bytes(img_bytes)
        img_b64 = base64.b64encode(img_resized).decode("utf-8")

        for attempt in range(3):
            try:
                response = client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": _DESCRIPTION_PROMPT},
                                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{img_b64}"}},
                            ],
                        }
                    ],
                    temperature=0.1,
                    max_tokens=256,
                    extra_body={"options": {"num_ctx": 4096}},
                )
                text = response.choices[0].message.content.strip()
                descriptions[img_id] = text if text else "[Empty description]"
                break
            except Exception as e:
                print(f"  Ollama error for {img_id}, attempt {attempt+1}: {e}")
                time.sleep(5)
        else:
            descriptions[img_id] = "[Description failed]"
    return descriptions


# --- Main entry point ---

_DEFAULT_MODELS = {
    "gemini": "gemini-2.0-flash",
    "openrouter": "openai/gpt-4o-mini",
    "groq": "llama-3.2-90b-vision-preview",
    "openai": "gpt-4o-mini",
    "ollama": "moondream",
}


def get_default_model() -> str:
    return os.environ.get("MODEL_NAME", _DEFAULT_MODELS.get(PROVIDER, "gemini-2.0-flash-001"))


def call_gemini(
    model_name: str,
    contents: list,
    system_instruction: str | None = None,
) -> dict:
    if PROVIDER == "gemini":
        return _call_gemini_direct(model_name, contents, system_instruction)
    return _call_openai_compat(model_name, contents, system_instruction)
