#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="${SCRIPT_DIR}/../backend"

if [[ -x "${SCRIPT_DIR}/.venv/bin/python" ]]; then
  PYTHON_BIN="${SCRIPT_DIR}/.venv/bin/python"
elif [[ -x "${BACKEND_DIR}/.venv/bin/python" ]]; then
  PYTHON_BIN="${BACKEND_DIR}/.venv/bin/python"
else
  PYTHON_BIN="python3"
fi

: "${WORKER_EXECUTOR_BACKEND:=comfyui_pipeline}"
: "${WORKER_HOST:=0.0.0.0}"
: "${WORKER_PORT:=8600}"
: "${WORKER_COMFYUI_URL:=http://127.0.0.1:8188}"
: "${WORKER_COMFYUI_POLL_INTERVAL_SEC:=2.0}"
: "${WORKER_COMFYUI_TIMEOUT_SEC:=1800}"
: "${WORKER_COMFYUI_LTXV_CHECKPOINT:=ltxv-2b-0.9.8-distilled-fp8.safetensors}"
: "${WORKER_COMFYUI_LTXV_CHECKPOINT_FALLBACK:=ltx-video-2b-v0.9.5.safetensors}"
: "${WORKER_COMFYUI_LTXV_TEXT_ENCODER:=t5xxl_fp16.safetensors}"
: "${WORKER_COMFYUI_IPADAPTER_MODEL:=ipAdapterPlusSd15_ipAdapterPlusSdxlVit.safetensors}"
: "${WORKER_COMFYUI_IPADAPTER_PLUS_FACE_MODEL:=ip-adapter-plus-face_sdxl_vit-h.safetensors}"
: "${WORKER_COMFYUI_IPADAPTER_FACEID_MODEL:=ip-adapter-faceid-plusv2_sdxl.bin}"
: "${WORKER_COMFYUI_IPADAPTER_FACEID_LORA:=ip-adapter-faceid-plusv2_sdxl_lora.safetensors}"
: "${WORKER_COMFYUI_CLIP_VISION_MODEL:=CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors}"

if [[ -z "${WORKER_PUBLIC_BASE_URL:-}" ]]; then
  echo "[ERROR] WORKER_PUBLIC_BASE_URL must be set for server deployment." >&2
  exit 1
fi

export WORKER_EXECUTOR_BACKEND
export WORKER_HOST
export WORKER_PORT
export WORKER_PUBLIC_BASE_URL
export WORKER_COMFYUI_URL
export WORKER_COMFYUI_POLL_INTERVAL_SEC
export WORKER_COMFYUI_TIMEOUT_SEC
export WORKER_COMFYUI_LTXV_CHECKPOINT
export WORKER_COMFYUI_LTXV_CHECKPOINT_FALLBACK
export WORKER_COMFYUI_LTXV_TEXT_ENCODER
export WORKER_COMFYUI_IPADAPTER_MODEL
export WORKER_COMFYUI_IPADAPTER_PLUS_FACE_MODEL
export WORKER_COMFYUI_IPADAPTER_FACEID_MODEL
export WORKER_COMFYUI_IPADAPTER_FACEID_LORA
export WORKER_COMFYUI_CLIP_VISION_MODEL

cd "${SCRIPT_DIR}"
exec "${PYTHON_BIN}" -m uvicorn app.main:app --app-dir "${SCRIPT_DIR}" --host "${WORKER_HOST}" --port "${WORKER_PORT}"
