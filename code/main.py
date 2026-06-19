import csv
import os
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

ROOT_DIR = SCRIPT_DIR.parent
OUTPUT_CSV = ROOT_DIR / "output.csv"

from pipeline.data_loader import load_claims, enrich_claim_row
from pipeline.evidence_lookup import lookup_evidence
from pipeline.history_lookup import lookup_history
from pipeline.prompt_templates import build_contents, build_system_instruction
from pipeline.gemini_client import call_gemini, describe_images, get_token_counts, reset_token_counts, get_default_model, PROVIDER
from pipeline.postprocess import postprocess
from pipeline.schema import OUTPUT_COLUMNS

DELAY_SECONDS = 0 if PROVIDER == "ollama" else 2
DESC_REFRESH_INTERVAL = 50


def _single_pass(rows, model_name):
    results = []
    for i, row in enumerate(rows):
        claim_object = row["claim_object"]
        evidence_texts = lookup_evidence(claim_object)
        history_context, history_is_risky = lookup_history(row["user_id"])

        contents = build_contents(
            claim_object=claim_object,
            chat_transcript=row["user_claim"],
            evidence_texts=evidence_texts,
            history_context=history_context,
            image_paths=row["image_paths_list"],
        )
        sys_inst = build_system_instruction(claim_object)

        model_output = call_gemini(model_name, contents, sys_inst)
        result = postprocess(model_output, claim_object, history_is_risky, row)
        results.append(result)

        print(f"  [{i+1}/{len(rows)}] {row['user_id']} - {result['claim_status']}")

        if i < len(rows) - 1:
            time.sleep(DELAY_SECONDS)

    return results


def _ollama_two_pass(rows, desc_model, analysis_model):
    print(f"Pass 1: Describing images with {desc_model}...")
    all_descriptions = {}
    for i, row in enumerate(rows):
        image_descriptions = describe_images(row["image_paths_list"], desc_model)
        all_descriptions[row["user_id"]] = image_descriptions
        print(f"  [{i+1}/{len(rows)}] {row['user_id']}: {len(image_descriptions)} images")
        if i < len(rows) - 1:
            time.sleep(1)

    print(f"\nPass 2: Analyzing with {analysis_model}...")
    results = []
    for i, row in enumerate(rows):
        claim_object = row["claim_object"]
        evidence_texts = lookup_evidence(claim_object)
        history_context, history_is_risky = lookup_history(row["user_id"])
        image_descriptions = all_descriptions.get(row["user_id"], {})

        contents = build_contents(
            claim_object=claim_object,
            chat_transcript=row["user_claim"],
            evidence_texts=evidence_texts,
            history_context=history_context,
            image_paths=row["image_paths_list"],
            image_descriptions=image_descriptions,
        )
        sys_inst = build_system_instruction(claim_object, image_descriptions=True)

        model_output = call_gemini(analysis_model, contents, sys_inst)
        result = postprocess(model_output, claim_object, history_is_risky, row,
                             image_descriptions=image_descriptions, evidence_texts=evidence_texts)
        results.append(result)

        print(f"  [{i+1}/{len(rows)}] {row['user_id']} - {result['claim_status']} ({result['issue_type']}/{result['object_part']})")

        if i < len(rows) - 1:
            time.sleep(1)

    return results


def process_csv(
    input_csv: str | Path,
    output_csv: str | Path,
    model_name: str | None = None,
):
    if model_name is None:
        model_name = get_default_model()

    reset_token_counts()
    df = load_claims(input_csv)
    rows = [enrich_claim_row(r) for r in df.to_dict("records")]

    print(f"Processing {len(rows)} claims with {PROVIDER}/{model_name}...")

    if PROVIDER == "ollama":
        desc_model = os.environ.get("DESC_MODEL", "moondream")
        analysis_model = model_name
        results = _ollama_two_pass(rows, desc_model, analysis_model)
    else:
        results = _single_pass(rows, model_name)

    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        for row in results:
            out_row = {col: row.get(col, "") for col in OUTPUT_COLUMNS}
            writer.writerow(out_row)

    tokens = get_token_counts()
    print(f"\nDone. Output: {output_csv}")
    print(f"API calls: {tokens['calls']}, prompt tokens: {tokens['prompt']}, completion tokens: {tokens['completion']}")

    return results


def main():
    if PROVIDER == "ollama":
        pass
    else:
        key_map = {"gemini": "GEMINI_API_KEY", "openrouter": "OPENROUTER_API_KEY", "groq": "GROQ_API_KEY", "openai": "OPENAI_API_KEY"}
        expected_key = key_map.get(PROVIDER, "")
        if expected_key and not os.environ.get(expected_key, ""):
            print(f"ERROR: {expected_key} not set.")
            sys.exit(1)

    input_csv = os.environ.get("INPUT_CSV", str(ROOT_DIR / "dataset" / "claims.csv"))
    output_csv = os.environ.get("OUTPUT_CSV", str(OUTPUT_CSV))
    model_name = os.environ.get("MODEL_NAME", None)

    process_csv(input_csv, output_csv, model_name)


if __name__ == "__main__":
    main()
