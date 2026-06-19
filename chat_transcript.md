# Chat Transcript — Multi-Modal Evidence Review

## System Development Summary

This transcript documents the iterative development process for the HackerRank Orchestrate challenge.

---

### Phase 1: Initial Setup

**User:** Set up the project with AGENTS.md onboarding, installed dependencies (openai, pillow, python-dotenv, pandas), and created initial pipeline structure.

**Agent:** Created `code/pipeline/` with schema.py, data_loader.py, evidence_lookup.py, history_lookup.py, prompt_templates.py, gemini_client.py, and postprocess.py. Created `code/main.py` entry point and `code/evaluation/` with metrics.py and main.py.

---

### Phase 2: Cloud API Integration (Gemini → OpenRouter → Groq)

**User:** Run the pipeline on sample claims.

**Agent:** Tested with Gemini API (gemini-2.5-flash-lite) — worked but free tier exhausted quickly. Switched to OpenRouter (gpt-4o-mini) — completed 19/20 sample claims. Switched to Groq (llama-3.2-90b-vision-preview) — also exhausted. All cloud free tiers consumed.

**Result:** 19/20 samples processed via gpt-4o-mini. Metrics: claim_status=65%, object_part=85%, valid_image=80%.

---

### Phase 3: Local Model Setup (Ollama)

**User:** Set up Ollama locally.

**Agent:** Installed Ollama v0.20.2. Pulled moondream (1B VLM, 1.7GB) and gemma4:e4b (8B text, 9.6GB). Discovered RTX 3050 Ti (4GB VRAM) constraints.

---

### Phase 4: moondream Single-Pass Failures

**User:** Run pipeline with moondream.

**Agent:** moondream crashed with full-resolution images (OOM on 4GB VRAM). Added image resizing (max 384px). moondream then ran but produced garbage output via /api/generate endpoint. Switched to OpenAI-compatible /v1/chat/completions endpoint — descriptions worked but structured JSON output failed (model ignored JSON instruction when images were present).

**Result:** Two-stage approach needed.

---

### Phase 5: Two-Stage Pipeline (moondream + gemma4:e4b)

**User:** Implement reliable pipeline.

**Agent:** 
- Stage 1: Describe each image individually with moondream (chat completions API, single image per call)
- Stage 2: Text-only analysis with gemma4:e4b using image descriptions as context
- Added intelligent defaults in postprocess.py for fields moondream can't output
- Added num_ctx=4096 for both models
- Simplified prompt template for local models (fill-in-the-blank JSON)

**Result:** Successful processing with varied outputs (supported/contradicted/not_enough_information across all claim types).

---

### Phase 6: Evaluation

**User:** Run full pipeline.

**Agent:** Processed all 44 claims (~5 min). Processed 20 sample claims for evaluation. Metrics on samples: claim_status=70%, object_part=90%, valid_image=90%, evidence_standard_met=85%.

**Final deliverables:**
- `code/main.py` — entry point
- `code/pipeline/` — modular pipeline components
- `code/evaluation/` — evaluation metrics and report
- `output.csv` — predictions for 44 test claims

---

*Total development time: ~3 hours (including testing, debugging, provider switching)*
