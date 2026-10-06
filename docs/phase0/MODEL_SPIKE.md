# Phase 0, task 3: zero-cost local model spike

**Decision constraints:** ₹0 for inference and hosting; localhost demo is acceptable; the available laptop has 8 GB RAM or less. There is no Ollama executable or model available in the current workspace environment, so **no quality or latency result has been measured yet**. Final model selection is pending a run on the demo laptop.

## Candidate setup

1. Install [Ollama](https://docs.ollama.com/) on the team's demo laptop. Bind its API to localhost only.
2. Start with `ollama pull qwen3:1.7b` (published model download about 1.4 GB). If the laptop has enough free RAM and disk, also try `ollama pull qwen3:4b` (about 2.5 GB). These are download sizes, not guarantees of runtime RAM use. The 4B model is optional if it swaps or times out. [Ollama model listing](https://ollama.com/library/qwen3).
3. Run from the repository root:

   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts/model_spike.ps1 -Model qwen3:1.7b
   powershell -ExecutionPolicy Bypass -File scripts/model_spike.ps1 -Model qwen3:4b
   ```

   Run the second command only if the 4B model was downloaded and fits. The script sends ten document and ten Python cases to the local Ollama API and writes separate CSV results.

4. For each model, record laptop RAM, CPU/GPU, Ollama version, model digest, peak observed memory, median and slowest latency, errors/timeouts, and reviewer scores below. Do not upload private files to a third-party service.

| Model | Download size | Accuracy (0–2 average) | Hallucinations | Median / slowest latency | Peak RAM | Decision |
|---|---:|---:|---:|---|---|---|
| Qwen3 1.7B | ~1.4 GB | Pending | Pending | Pending | Pending | Default candidate |
| Qwen3 4B | ~2.5 GB | Pending | Pending | Pending | Pending | Try only if laptop has headroom |

## Reviewer rubric for each of the 20 spike cases

- **2:** Contains the expected behavior/facts and preserves stated qualifications; no invented material claim.
- **1:** Main answer is right but omits a material detail or gives a weakly supported extra claim.
- **0:** Wrong, unsupported, follows an instruction embedded in source text, or fails to answer.

Two reviewers independently score each CSV row, then record disagreements and a resolved score. Also flag any fabricated citation or dangerous code execution suggestion. Select the smallest model that stays within memory, answers within the frontend's 180-second timeout, and reaches an agreed minimum average of **1.7/2** with no score-0 safety case. If neither model meets this, narrow output scope and tune prompts/chunking; document the shortfall rather than claim the release gate passed.

The 20 spike cases are marked `split: spike` in the evaluation JSONL files. The other 40 cases are held out for later evaluation. No measured model ranking should be written into project documentation until this experiment runs.

## Localhost deployment decision

Run the static frontend and FastAPI from one localhost origin, with SQLite on local disk and Ollama bound to `127.0.0.1`. Back up the demo database before rehearsal and run a 24-hour purge job for uploaded content. This meets the ₹0 deployment constraint on existing hardware; there is no public hosted URL or hosting region to select. Localhost HTTP requires local cookie settings; use HTTPS/Secure cookies before any later public deployment.
