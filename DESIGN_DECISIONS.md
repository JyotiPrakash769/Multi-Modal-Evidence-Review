# Multi-Modal Evidence Review — Design Decisions & Route Taken

## Why We Built It This Way

### The Starting Point

We had 44 damage claims (cars, laptops, packages). Each claim had:
- A chat transcript describing the damage
- 1-3 images of the damaged object
- User claim history (past claims, risk flags)
- Evidence requirements (minimum image standards)

We needed to output a structured JSON decision per claim: what part is damaged, what type of issue, supported/contradicted/insufficient, severity, etc.

### Why Not a Single VLM Call?

**The obvious approach**: Send everything (chat + all images + evidence rules + user history) to a vision model in one prompt. Get JSON back. Done.

This worked with cloud APIs (GPT-4o-mini, Gemini) — 70% accuracy. But then all cloud free tiers ran out.

### Why Not Cloud APIs?

We tried three providers:
| Provider | Result |
|----------|--------|
| **Gemini** | Free tier exhausted after ~20 calls |
| **OpenRouter** | $1 free credits exhausted after ~19 calls |
| **Groq** | Free tier exhausted after ~30 calls |

All required paid credits to continue. Budget: $0.

### The Local-Only Constraint

Only available hardware: **NVIDIA RTX 3050 Ti with 4GB VRAM**.

Ollama could serve models locally. Two models were small enough:
| Model | Size | VRAM | Can See Images? | Can Output JSON? |
|-------|------|------|-----------------|------------------|
| **moondream** | 1.7 GB | 1.3 GB | Yes (VLM) | No (too small) |
| **gemma4:e4b** | 9.6 GB | 0 GB (runs in system RAM) | No (text-only) | Yes (8B params) |

**Neither alone could do the job.** Moondream could describe images but couldn't follow structured JSON instructions. Gemma could reason and output JSON but couldn't see images.

### Why Two Stages?

The solution: let each model do what it's good at.

```
Stage 1: moondream ──► Image descriptions (free-form text)
Stage 2: gemma4:e4b ──► Text analysis → structured JSON
```

This split was not the first choice — it was forced by the hardware constraint. A single 7B VLM (like LLaVA) would do both stages in one call, but it wouldn't fit in 4GB VRAM.

### Why the Endpoint Switch Mattered

Ollama offers two API endpoints:

| Endpoint | Result with moondream |
|----------|----------------------|
| `/api/generate` | Produced garbage: `"urn..."`, `"!!!IMAGE NOT GENERATED!!!"` |
| `/v1/chat/completions` (OpenAI-compatible) | Produced coherent descriptions: `"The image shows a white car with a visible scratch on the front bumper"` |

Switching to the OpenAI-compatible endpoint was a critical fix. The `/api/generate` endpoint apparently doesn't handle multimodal prompts the same way.

### Why Image Resizing?

Initial tests with any image caused:
```
"model runner has unexpectedly stopped, this may be due to resource limitations"
```

The CLIP vision encoder in moondream was running out of VRAM on full-resolution images. Resizing to **max 384px** on the longest side (with Pillow, LANCZOS filter) solved it.

Even a 32KB JPEG would crash the model. After resizing, it worked every time.

### Why the Minimalist Prompt?

gemma4:e4b has a default context window of **2048 tokens**. Our first prompt was a verbose system instruction with 10+ rules, chain-of-thought, and a full JSON schema. The model either ignored it or produced partial output.

We stripped it down to:
```
Fill this JSON:
{"issue_type": "___", "object_part": "___", "claim_status": "___", "severity": "___"}
```

With allowed values listed above it. This worked because:
- gemma4:e4b is an instruction-tuned model
- Fill-in-the-blank is the simplest form of structured output
- No complex reasoning, no chain-of-thought — just value selection

We also increased `num_ctx` to 4096 via Ollama options.

### Why Rule-Based Defaults for Half the Fields?

gemma4:e4b only outputs 4 fields (issue_type, object_part, claim_status, severity) — the core fields that require visual-textual reasoning.

The other 6 fields are deterministic rules:

| Field | Rule |
|-------|------|
| `valid_image` | "true" if description calls succeeded |
| `evidence_standard_met` | "true" if ≥1 valid image description |
| `evidence_standard_met_reason` | "X valid images provided" |
| `supporting_image_ids` | All image IDs that were described |
| `claim_status_justification` | "Claim {status} for {part} damage" |
| `risk_flags` | "manual_review_required" + user_history_risk if flagged |

A larger model could output all 10 fields. But with 4GB VRAM and no budget, this is the best we could do.

### What We'd Do Differently

1. **Cloud API with budget**: $0.18 for GPT-4o-mini would give single-pass, higher accuracy, all 10 fields
2. **Better local VLM**: If hardware had 8GB+ VRAM, LLaVA-NeXT (7B) or Qwen2-VL (7B) could do both stages in one
3. **ONNX / quantization**: Running a quantized 7B VLM could fit in 4GB with reduced quality
4. **Fine-tuning**: A fine-tuned small model could match larger model accuracy for this specific task

### The Trade-Off We Accepted

| Cloud API approach | Our local approach |
|---|---|
| Single call per claim | ~4 calls per claim |
| ~3s per claim | ~7s per claim |
| $0.18 for 44 claims | $0.00 |
| All 10 fields from model | 4 fields from model, 6 from rules |
| ~80% accuracy (estimated) | 70% accuracy |

Zero cost, zero API dependency, fully reproducible on any machine with Ollama.

### Files

| File | Purpose |
|------|---------|
| `code/main.py` | Entry point — orchestrates two-pass pipeline |
| `code/pipeline/gemini_client.py` | `describe_images()` + `call_gemini()` |
| `code/pipeline/prompt_templates.py` | Prompt builders (local vs cloud variants) |
| `code/pipeline/postprocess.py` | Validation + rule-based defaults |
| `code/pipeline/schema.py` | Allowed values, output column definitions |
| `code/evaluation/` | Metrics, evaluation runner, report |
| `output.csv` | Final predictions for 44 claims |
