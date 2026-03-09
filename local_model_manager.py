"""
Local LLM model manager for offline invoice extraction.

Manages downloading, loading, and running a small GGUF model
(Qwen2.5-0.5B-Instruct) via llama-cpp-python.
"""

import logging
import os
import shutil
from pathlib import Path

from config import LOCAL_MODEL_DIR

logger = logging.getLogger(__name__)

# Model configuration
MODEL_REPO = "Qwen/Qwen2.5-0.5B-Instruct-GGUF"
MODEL_FILENAME = "qwen2.5-0.5b-instruct-q4_k_m.gguf"

# Cached model instance
_llm_instance = None


def get_model_dir() -> Path:
    """Get the model storage directory, creating it if needed."""
    model_dir = Path(LOCAL_MODEL_DIR)
    model_dir.mkdir(parents=True, exist_ok=True)
    return model_dir


def _get_model_path() -> Path:
    """Get the full path to the GGUF model file."""
    return get_model_dir() / MODEL_FILENAME


def is_model_downloaded() -> bool:
    """Check if the GGUF model file exists on disk."""
    return _get_model_path().is_file()


def get_model_status() -> dict:
    """Get current model status information."""
    model_path = _get_model_path()
    downloaded = model_path.is_file()
    size_mb = round(model_path.stat().st_size / (1024 * 1024)) if downloaded else 0
    return {
        "downloaded": downloaded,
        "model_name": MODEL_FILENAME,
        "size_mb": size_mb,
    }


def download_model():
    """Download the GGUF model from HuggingFace Hub."""
    from huggingface_hub import hf_hub_download

    logger.info(f"Downloading model {MODEL_REPO}/{MODEL_FILENAME} ...")
    model_dir = get_model_dir()

    hf_hub_download(
        repo_id=MODEL_REPO,
        filename=MODEL_FILENAME,
        local_dir=str(model_dir),
    )
    logger.info(f"Model downloaded to {model_dir / MODEL_FILENAME}")


def delete_model():
    """Remove the downloaded model file and clear the cached instance."""
    global _llm_instance
    _llm_instance = None

    model_path = _get_model_path()
    if model_path.is_file():
        model_path.unlink()
        logger.info(f"Deleted model file: {model_path}")

    # Also clean up any huggingface cache metadata
    for f in get_model_dir().iterdir():
        if f.name.startswith(".") or f.suffix in (".json", ".lock"):
            if f.is_dir():
                shutil.rmtree(f, ignore_errors=True)
            else:
                f.unlink(missing_ok=True)


def load_model():
    """
    Load the GGUF model into memory (singleton).
    Returns the Llama instance.
    """
    global _llm_instance
    if _llm_instance is not None:
        return _llm_instance

    model_path = _get_model_path()
    if not model_path.is_file():
        raise FileNotFoundError(
            f"Model not found at {model_path}. Please download it first."
        )

    from llama_cpp import Llama

    logger.info(f"Loading model from {model_path} ...")
    _llm_instance = Llama(
        model_path=str(model_path),
        n_ctx=4096,
        n_threads=max(1, (os.cpu_count() or 1) // 2),
        verbose=False,
    )
    logger.info("Model loaded successfully")
    return _llm_instance


def generate(prompt: str, max_tokens: int = 1024) -> str:
    """
    Run inference on the loaded model.

    Args:
        prompt: The text prompt to send to the model.
        max_tokens: Maximum tokens to generate.

    Returns:
        Generated text string.
    """
    llm = load_model()
    output = llm.create_chat_completion(
        messages=[
            {"role": "system", "content": "You are a helpful assistant that extracts structured data from text. Always respond with valid JSON only, no other text."},
            {"role": "user", "content": prompt},
        ],
        max_tokens=max_tokens,
        temperature=0.1,
    )
    content = output["choices"][0]["message"]["content"]  # type: ignore[index]
    return content or ""
