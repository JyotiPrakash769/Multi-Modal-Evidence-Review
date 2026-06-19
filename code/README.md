# HackerRank Orchestrate — Multi-Modal Evidence Review

A system that verifies visual evidence for damage claims (cars, laptops, packages) using local or cloud vision LLMs.

## Setup

1. **Install Ollama** (https://ollama.com) and pull models:
   ```
   ollama pull moondream
   ollama pull gemma4:e4b
   ```

2. **Configure** `code/.env`:
   ```
   PROVIDER=ollama
   MODEL_NAME=gemma4:e4b
   DESC_MODEL=moondream
   ```

3. **Install dependencies:**
   ```
   pip install -r code/requirements.txt
   ```

## Usage

### Run on test claims (produces `output.csv`)
```
cd code
python main.py
```

The pipeline uses a two-pass approach for Ollama:
- **Pass 1**: Describe each image individually using `moondream` (1B VLM)
- **Pass 2**: Analyze all descriptions with `gemma4:e4b` (8B text LLM) to produce structured JSON

### Run evaluation on sample claims
```
cd code
python -m evaluation.main
```

### Cloud providers (alternative)
Set env vars in `.env`:
```
PROVIDER=openrouter
OPENROUTER_API_KEY=sk-or-...
MODEL_NAME=openai/gpt-4o-mini
```

## Architecture

```
code/
├── main.py                          # Entry point (two-pass for Ollama, single-pass for cloud)
├── pipeline/
│   ├── data_loader.py               # CSV/image loading
│   ├── evidence_lookup.py           # Evidence requirements by claim_object
│   ├── history_lookup.py            # User history risk assessment
│   ├── prompt_templates.py          # System instruction + per-claim content builder
│   ├── gemini_client.py             # Multi-provider LLM API wrapper + image descriptions
│   ├── postprocess.py               # Validate/fix model output, build risk_flags
│   └── schema.py                    # Allowed values and output column definitions
├── evaluation/
│   ├── main.py                      # Evaluation runner
│   ├── metrics.py                   # Accuracy and Jaccard scoring
│   └── evaluation_report.md         # Generated report
└── requirements.txt
```

## Design decisions

- **Local-first** – Uses Ollama for fully offline processing with zero API costs.
- **Two-pass pipeline** – Image descriptions (moondream) + text analysis (gemma4:e4b) because moondream is too small for structured JSON output when images are present.
- **Image resizing** – Images resized to max 384px to fit 4GB VRAM (RTX 3050 Ti).
- **Deterministic post-processing** – Model output is validated against allowed-value lists and filled with intelligent defaults.
- **Provider-agnostic** – OpenAI-compatible API format means you can swap between Ollama, Groq, OpenRouter, or OpenAI.
- **User history as context** – History flags are surfaced to the model but labeled as "context only" to prevent overriding visual evidence.

## Performance (Ollama on RTX 3050 Ti / 4GB VRAM)

| Metric | Value |
|--------|-------|
| Sample claims (20) | ~141s |
| Test claims (44) | ~311s |
| Cost | $0.00 (local) |
| Claim status accuracy | 70% (on sample) |
| Object part accuracy | 90% (on sample) |
| Valid image accuracy | 90% (on sample) |
