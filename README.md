# Multi-Modal Evidence Review — HackerRank Orchestrate

---

## Part 1: The Problem Statement

### What We Were Asked to Build

A system that verifies damage claims using images, a short claim conversation, user history, and minimum evidence requirements. Each claim is about one of three object types: **car**, **laptop**, or **package**.

The system must decide whether the submitted images **support** the user's claim, **contradict** it, or do **not provide enough information**.

### What the System Should Do (per claim)

- Extract the actual damage claim from the conversation
- Inspect one or more submitted images
- Decide whether the image evidence is sufficient
- Identify the visible issue type
- Identify the relevant object part
- Decide whether the claim is supported, contradicted, or lacks information
- Select the image IDs that support the decision
- Flag image quality, mismatch, authenticity, or user-history risks
- Estimate severity
- Produce short justifications grounded in the images

### Input Files Provided

| File | Description |
|------|-------------|
| `dataset/claims.csv` | 44 input-only claims (user_id, image_paths, user_claim, claim_object) |
| `dataset/sample_claims.csv` | 20 labeled examples with expected outputs for evaluation |
| `dataset/user_history.csv` | Historical claim counts and risk patterns per user |
| `dataset/evidence_requirements.csv` | Minimum image evidence checklist by object and issue family |
| `dataset/images/sample/` | Images referenced by sample_claims.csv |
| `dataset/images/test/` | Images referenced by claims.csv |

### Required Output (output.csv)

14 columns per row:

| Column | Meaning |
|--------|---------|
| `evidence_standard_met` | Whether image set is sufficient (`true`/`false`) |
| `evidence_standard_met_reason` | Short reason for evidence decision |
| `risk_flags` | Semicolon-separated flags, or `none` |
| `issue_type` | Visible issue (dent, scratch, crack, etc.) |
| `object_part` | Relevant part (front_bumper, screen, box, etc.) |
| `claim_status` | `supported`, `contradicted`, or `not_enough_information` |
| `claim_status_justification` | Image-grounded explanation |
| `supporting_image_ids` | Image IDs supporting the decision, or `none` |
| `valid_image` | Whether image set is usable (`true`/`false`) |
| `severity` | `none`, `low`, `medium`, `high`, or `unknown` |

### Allowed Values

- **Claim status**: supported, contradicted, not_enough_information
- **Issue type**: dent, scratch, crack, glass_shatter, broken_part, missing_part, torn_packaging, crushed_packaging, water_damage, stain, none, unknown
- **Car parts**: front_bumper, rear_bumper, door, hood, windshield, side_mirror, headlight, taillight, fender, quarter_panel, body, unknown
- **Laptop parts**: screen, keyboard, trackpad, hinge, lid, corner, port, base, body, unknown
- **Package parts**: box, package_corner, package_side, seal, label, contents, item, unknown
- **Risk flags**: blurry_image, cropped_or_obstructed, low_light_or_glare, wrong_angle, wrong_object, wrong_object_part, damage_not_visible, claim_mismatch, possible_manipulation, non_original_image, text_instruction_present, user_history_risk, manual_review_required
- **Severity**: none, low, medium, high, unknown

### Evaluation Requirement

- Evaluate on `dataset/sample_claims.csv` (20 labeled rows) before producing final predictions
- Include evaluation code in `code/`
- Generate operational analysis: model calls, token usage, cost, runtime, rate limiting

### Submission Deliverables

| File | Description |
|------|-------------|
| `code.zip` | Full runnable solution with README, prompts/configs, evaluation folder |
| `output.csv` | Predictions for all 44 rows in claims.csv |
| `chat_transcript` | Conversation transcript showing how the system was developed |

---

## Part 2: How I Solved It

### Constraints We Faced

1. **No cloud API budget**: Gemini, OpenRouter, and Groq free tiers were all exhausted. Every cloud option required paid credits.
2. **Limited hardware**: NVIDIA RTX 3050 Ti with only **4GB VRAM**. Most vision models (7B+) don't fit.
3. **Two local models available**: `moondream` (1B params, vision-capable, 1.7GB) and `gemma4:e4b` (8B params, text-only, 9.6GB).
4. **Neither alone could do the job**: moondream can see images but is too small for structured JSON reasoning. gemma4:e4b can reason well but cannot see images.

### Our Solution: Two-Stage Local Pipeline

We split the problem into two stages, each using the model best suited for it:

```
Stage 1 (moondream)                          Stage 2 (gemma4:e4b)
┌─────────────────────┐                      ┌──────────────────────────┐
│ For each image:     │                      │ Build text-only prompt:  │
│                     │                      │  - Chat transcript       │
│ Send to moondream   │──── descriptions ──► │  - Image descriptions    │
│ "Describe damage"   │                      │  - Evidence requirements │
│                     │                      │  - User history          │
│ Returns:            │                      │  - Allowed values        │
│ free-form text      │                      │                          │
│ description         │                      │ Send to gemma4:e4b       │
└─────────────────────┘                      │                          │
                                             │ Returns: structured JSON │
                                             │ {"issue_type",           │
                                             │  "object_part",          │
                                             │  "claim_status",         │
                                             │  "severity"}             │
                                             └──────────────────────────┘
                                                         │
                                                         ▼
                                              ┌──────────────────────┐
                                              │ Postprocess:         │
                                              │ fill remaining fields│
                                              │ with rule defaults   │
                                              │ (valid_image,        │
                                              │  evidence_standard,  │
                                              │  supporting_ids,     │
                                              │  risk_flags)         │
                                              └──────────────────────┘
                                                         │
                                                         ▼
                                                   output.csv
                                              (44 rows, 14 columns)
```

### Key Technical Decisions

**1. Two-pass pipeline instead of single-pass**
moondream ignores JSON output instructions when images are present in the prompt. By separating image description (free-form text, no JSON required) from analysis (text-only, no images), both models work as intended.

**2. OpenAI-compatible API endpoint**
Ollama offers two APIs. The `/api/generate` endpoint produced garbage descriptions like `"urn..."` and `"!!!IMAGE NOT GENERATED!!!"`. Switching to the OpenAI-compatible `/v1/chat/completions` endpoint fixed this immediately.

**3. Image resizing to 384px**
Full-resolution images caused `"model runner has unexpectedly stopped"` errors due to OOM on 4GB VRAM. Resizing to max 384px on the longest side solved it without losing visible damage cues.

**4. Simplified prompt for local models**
gemma4:e4b has 2048 context tokens by default. We increased it to 4096 and stripped the prompt to essentials: a fill-in-the-blank JSON template with allowed values listed inline. No lengthy system instructions, no chain-of-thought.

**5. Rule-based defaults for auxiliary fields**
The 8B model only outputs 4 fields (issue_type, object_part, claim_status, severity) reliably. The remaining 6 fields are filled with intelligent defaults:
- `valid_image`: "true" if descriptions succeeded
- `evidence_standard_met`: "true" if at least 1 valid image
- `supporting_image_ids`: all successfully described image IDs
- `claim_status_justification`: auto-generated from status + part
- `risk_flags`: `manual_review_required` + `user_history_risk` if flagged

### Technologies Used

| Technology | Role |
|------------|------|
| **Python 3.12** | Main programming language |
| **Ollama v0.20.2** | Local model server (http://localhost:11434) |
| **moondream** (1B VLM) | Stage 1 — image description generation |
| **gemma4:e4b** (8B LLM) | Stage 2 — structured claim analysis |
| **openai** Python library | OpenAI-compatible API calls to Ollama |
| **Pillow** | Image resizing to fit 4GB VRAM |
| **pandas** | CSV data loading (claims, history, evidence) |
| **python-dotenv** | Environment configuration |
| **RTX 3050 Ti (4GB VRAM)** | Hardware for local inference |

### Performance

| Metric | Value |
|--------|-------|
| **Total runtime (44 claims)** | ~311 seconds (~5 min) |
| **Runtime per claim** | ~7 seconds |
| **Total cost** | **$0.00** (fully local, no API calls) |
| **API calls** | 44 analysis + ~85 image descriptions = ~129 total |
| **Prompt tokens** | ~27,500 |
| **Completion tokens** | ~1,500 |
| **Images processed** | 85 (44 claims × 1-3 images each) |

**Accuracy on sample claims (20 rows):**

| Field | Accuracy |
|-------|----------|
| Claim Status | 70% (14/20) |
| Issue Type | 45% (9/20) |
| Object Part | 90% (18/20) |
| Severity | 55% (11/20) |
| Evidence Standard Met | 85% (17/20) |
| Valid Image | 90% (18/20) |

### What We'd Improve

1. **Better image descriptions**: moondream is only 1B params. A model like LLaVA-NeXT (7B) or Qwen2-VL (7B) would capture more subtle damage but won't fit in 4GB VRAM.
2. **Full schema output**: The 8B model should output all 10 fields. Fine-tuning or a better prompt might achieve this.
3. **Risk flag detection**: Currently rule-based. A VLM could detect blurry images, wrong angles, or manipulation.
4. **Cost comparison**: Cloud VLMs (GPT-4o-mini) would cost ~$0.004/claim = $0.18 total but need paid credits.

### How to Run

```bash
# Prerequisites
ollama pull moondream
ollama pull gemma4:e4b
pip install -r code/requirements.txt

# Run the pipeline
cd C:\Users\jyoti\hackerrank-orchestrate-june26
python code\main.py

# Output: output.csv (44 rows, 14 columns)
# Progress: prints [1/44], [2/44], ... with each claim's result
```

### Repository Structure

```
├── code/
│   ├── main.py                       # Entry point (two-pass + single-pass)
│   ├── pipeline/
│   │   ├── data_loader.py            # CSV loading
│   │   ├── evidence_lookup.py        # Evidence requirements
│   │   ├── gemini_client.py          # VLM/LLM API + describe_images()
│   │   ├── history_lookup.py         # User history
│   │   ├── postprocess.py            # Validation + defaults
│   │   ├── prompt_templates.py       # Prompt builders
│   │   ├── schema.py                 # Allowed values
│   │   └── __init__.py
│   ├── evaluation/
│   │   ├── main.py                   # Evaluation runner
│   │   ├── metrics.py                # Accuracy scoring
│   │   └── evaluation_report.md      # Generated report
│   └── README.md
├── dataset/
│   ├── claims.csv                    # 44 test claims
│   ├── sample_claims.csv             # 20 labeled samples
│   ├── user_history.csv              # User risk data
│   ├── evidence_requirements.csv     # Evidence rules
│   └── images/                       # Sample + test images
├── output.csv                        # Final predictions
├── chat_transcript.md                # Development log
├── problem_statement.md              # Full task spec
├── AGENTS.md                         # AI tool rules
└── README.md                         # You are here
```
