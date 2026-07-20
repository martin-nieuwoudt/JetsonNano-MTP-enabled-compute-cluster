Adjusting Model Temperature in llama.cpp

## Executive Summary
This report outlines how to configure the generation temperature parameter in `llama.cpp`. Temperature directly modulates the probability distribution of predicted tokens, controlling the balance between predictability (factual accuracy) and randomness (creativity). 

---

## 1. Parameter Specifications
* **Command Flag:** `--temp` (note: `-t` is **threads**, not temperature, in all llama.cpp versions)
* **API Key:** `"temperature"`
* **Default:** `0.1` (Values above `1.0` highly risk text degradation)


### Target Use Cases

* **`0.1` (Deterministic / Greedy):** Ideal for coding, math, structured logic, and data extraction.


---

## 2. Implementation Methods

### Method A: Command Line Interface (`llama-cli`)
Pass the flag directly to the terminal binary during execution.

```bash
# Example 1: Factual/Deterministic Mode
./llama-cli -m model.gguf --temp 0.1 -p "Convert this text to JSON:"

```

### Method B: API Server (`llama-server`)
When serving models locally or in production, configure temperature via JSON payloads or server configuration files.

#### API Request Payload (`POST /v1/chat/completions`)
```json
{
  "model": "your-model-name",
  "messages": [
    {
      "role": "user",
      "content": "Write an executive summary of quantum computing."
    }
  ],
  "temperature": 0.1
}
```

#### Server Configuration
`llama-server` is configured via CLI flags (the same `--temp` flag as the CLI) or a server config file passed with `--config`. It does **not** read a `[model_config]` `config.ini` with a `temp =` key. Example using the flag directly:

```bash
./llama-server -m /path/to/model.gguf --temp 0.1
```

To set a default for all requests, pass `--temp` at launch; individual API requests can still override it via the `"temperature"` field in the JSON payload.

### Method C: Python Bindings (`llama-cpp-python`)
Specify the temperature variable dynamically during text generation functions.

```python
from llama_cpp import Llama

# 1. Initialize Model
llm = Llama(model_path="./model.gguf")

# 2. Generate text with low temperature for code logic
output = llm(
    "Write a Python function to reverse a string.", 
    temperature=0.1
)
print(output["choices"][0]["text"])
```

---

## 3. Best Practices & Advanced Sampling
Changing the temperature alone can sometimes cause the model to repeat words or hallucinate gibberish at high ranges. Combine temperature with the following options for optimal stability:

1. **`--min-p` (Minimum Probability):** Set to `0.05`. It dynamically cuts off tokens that are too unlikely, keeping high-temperature text coherent.
2. **`--top-p` (Nucleus Sampling):** Set to `0.9`. It limits the token pool to the top 90% cumulative probability mass.
3. **`--repeat-penalty`:** Set between `1.0` and `1.2`. It stops low-temperature outputs from getting stuck in an infinite loop.

---

## 4. Cluster Deployment — Deterministic Profile (2026-07-20)

The 11-node Jetson Nano cluster runs a **fixed deterministic sampling profile** — these values are the single source of truth in `code/mcp/cluster_settings.json` and are enforced end-to-end (model load → chat → ensemble). They are **never** changed for "creativity" tuning; the cluster is a deterministic inference engine, not a chatbot.

| Parameter | Value | Flag | Notes |
|-----------|-------|------|-------|
| `temp` | `0.1` | `--temp` | Deterministic / greedy — coding, math, structured logic, data extraction |
| `min_p` | `0.05` | `--min-p` | Cuts off too-unlikely tokens, keeps low-temp output coherent |
| `top_p` | `0.9` | `--top-p` | Nucleus sampling — top 90% cumulative probability mass |
| `repeat_penalty` | `1.1` | `--repeat-penalty` | Prevents low-temp repetition loops |

**Enforcement chain (verified 2026-07-20):**
- `code/mcp/cluster_settings.json` → `sampling` block is the canonical source.
- `code/cluster_telemetry.py` captures `_RESIDENT_SAMPLING` at model load and reuses it for every `/completion` and ensemble member (previously dropped → stale defaults; now fixed).
- `code/cluster_server.py` `cmd_ensemble_start` passes the same values as `--temp`/`--min-p`/`--top-p`/`--repeat-penalty`.
- Dashboard `/api/sampling` returns `{"temp":0.1,"min_p":0.05,"top_p":0.9,"repeat_penalty":1.1,"ctx_size":4096,"max_tokens":4096}`.

> **Invariant:** these four values are a platform constant. Do not edit them in code, the dashboard, or API payloads — change them only in `code/mcp/cluster_settings.json`.