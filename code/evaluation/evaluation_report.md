# Evaluation Report
**Date:** 2026-06-19T23:54:13+0530
**Pipeline:** moondream (descriptions) + gemma4:e4b (analysis)
**Total samples:** 20
**Total images:** 29
**Total runtime:** 141.5s

---

## Metrics

- **Claim Status:** 14/20 (70.0%)
- **Issue Type:** 9/20 (45.0%)
- **Object Part:** 18/20 (90.0%)
- **Severity:** 11/20 (55.0%)
- **Evidence Standard Met:** 17/20 (85.0%)
- **Valid Image:** 18/20 (90.0%)
- **Risk Flags Jaccard:** 0.417
- **Supporting Image Ids Jaccard:** 0.750
---

## Operational Analysis

- **API calls (analysis):** 20 (1 per claim)
- **Image description calls:** ~29 (1 per image via moondream)
- **Total model calls:** ~49
- **Prompt tokens:** 12044
- **Completion tokens:** 669
- **Images processed:** 29
- **Runtime:** 141.5s for 20 samples (7.1s per claim)
- **Estimated cost:** $0.00 (fully local, no API costs)

### Model Details

- **Description model:** `moondream` (1B params, ~1.7GB, run locally via Ollama)
- **Analysis model:** `gemma4:e4b` (8B params, ~9.6GB, run locally via Ollama)
- **Hardware:** NVIDIA RTX 3050 Ti (4GB VRAM) + system RAM
- **Provider:** Local Ollama v0.20.2

### Rate Limiting & Latency

- **Sequential processing:** 1-second delay between claims to allow model context switching
- **Retry logic:** 3 retries per call for transient errors
- **Image resizing:** Images resized to max 384px to fit 4GB VRAM constraints
- **Context window:** `num_ctx=4096` for both models
- **TPM/RPM:** N/A (local, no rate limits)
- **Total estimated runtime for 44 claims:** ~311s (~5 min)

### Cost Analysis

Since both models run entirely locally via Ollama, there are zero API costs.
The only cost is electricity (~100-200W during inference).
For comparison, equivalent cloud API cost (GPT-4o-mini): ~$0.004 per claim = ~$0.18 for 44 claims.

### Limitations

- `moondream` (1B VLM) produces basic image descriptions and may miss subtle damage.
- `gemma4:e4b` (8B) fits in system RAM rather than VRAM, causing ~30-40s cold start.
- Two-pass pipeline doubles runtime vs single-pass cloud API.
- `risk_flags` and `supporting_image_ids` use rule-based defaults, not model output.
