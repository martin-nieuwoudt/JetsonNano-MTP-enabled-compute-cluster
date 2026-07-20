# Makes `code/mcp` a regular package so it is preferred over the unrelated
# `mcp` SDK package installed in the venv. Without this, `import mcp.cluster_config`
# inside the venv resolves to the SDK and cluster_infer.py / cluster_qos.py silently
# fall back to hardcoded defaults (losing BUILD_VARIANTS, MODELS, etc.).
