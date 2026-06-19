# Multi-Modal Evidence Review — HackerRank Orchestrate

A system that verifies visual evidence for damage claims (cars, laptops, packages) using chat transcripts, images, user history, and evidence requirements.

Built for the **HackerRank Orchestrate** 24-hour hackathon (June 2026).

## Our Approach

We use a **two-stage local pipeline** with Ollama because cloud API free tiers (Gemini, OpenRouter, Groq) were exhausted.

### Stage 1 — Image Descriptions (moondream)
For each claim, send each image individually to `moondream` (1B VLM) with a description prompt. Collects free-form text descriptions describing visible damage.

### Stage 2 — Structured Analysis (gemma4:e4b)
Build a text-only prompt with:
- Image descriptions from Stage 1
- Chat transcript
- Evidence requirements
- User history
- Allowed value lists

Send to `gemma4:e4b` (8B text LLM) which outputs structured JSON: `issue_type`, `object_part`, `claim_status`, `severity`.

### Post-processing
Fill remaining fields (`valid_image`, `evidence_standard_met`, `supporting_image_ids`, `risk_flags`) with rule-based defaults since the 8B model only outputs 4 fields reliably.

## Architecture

```
├── code/
│   ├── main.py                    # Entry point (two-pass pipeline)
│   ├── pipeline/
│   │   ├── gemini_client.py       # Multi-provider API + describe_images()
│   │   ├── prompt_templates.py    # Prompt builders (cloud vs local)
│   │   ├── postprocess.py         # Validation + intelligent defaults
│   │   ├── schema.py              # Allowed values + output schema
│   │   ├── data_loader.py         # CSV loading
│   │   ├── evidence_lookup.py     # Evidence requirements
│   │   └── history_lookup.py      # User history risk
│   ├── evaluation/
│   │   ├── main.py                # Evaluation runner
│   │   ├── metrics.py             # Accuracy scoring
│   │   └── evaluation_report.md   # Generated report
│   └── README.md
├── output.csv                     # Predictions for 44 claims
├── chat_transcript.md             # Development conversation
├── problem_statement.md           # Full task spec
└── AGENTS.md                      # AI tool rules
```

## Technologies Used

| Technology | Purpose |
|------------|---------|
| Python 3.12 | Main language |
| Ollama v0.20.2 | Local model server |
| moondream (1B VLM) | Image description generation |
| gemma4:e4b (8B LLM) | Structured claim analysis |
| openai (Python lib) | OpenAI-compatible API calls |
| Pillow | Image resizing (384px max for 4GB VRAM) |
| pandas | CSV data loading |
| RTX 3050 Ti (4GB) | Hardware (local inference) |

## Performance

| Metric | Sample Claims (20) | Test Claims (44) |
|--------|-------------------|------------------|
| Runtime | ~141s | ~311s (5 min) |
| Cost | $0 (local) | $0 (local) |
| Claim Status Acc | 70% | - |
| Object Part Acc | 90% | - |
| Valid Image Acc | 90% | - |

## How to Run

```bash
# Prerequisites: Ollama installed + models pulled
ollama pull moondream
ollama pull gemma4:e4b
pip install -r code/requirements.txt

# Run pipeline
python code/main.py
# Output: output.csv
```

## Key Decisions

- **Two-pass over single-pass**: moondream ignores JSON instructions when images are present in prompts. Separating description (free-form) from analysis (text-only JSON) lets each model do what it's good at.
- **Local over cloud**: All three cloud providers' free credits exhausted. Local models are slower but cost $0 and have no rate limits.
- **Image resizing**: Full-resolution images caused OOM on 4GB VRAM. Resizing to 384px max solved this.
- **Endpoint choice**: Ollama's `/api/generate` produced garbage descriptions. Switching to OpenAI-compatible `/v1/chat/completions` fixed it.

## Submission

- `output.csv` — 44 predictions (14 columns)
- `code.zip` — runnable solution
- `chat_transcript.md` — dev conversation
