"""
Download the SmartStudy AI model from HuggingFace and register it with Ollama.

Usage:
    python setup_model.py

This script:
  1. Downloads the GGUF model from HuggingFace (if not already present)
  2. Creates the Ollama model 'smartstudy_ai' using the Modelfile
  3. Creates the Ollama model 'kdu_advisor' using the Modelfile_llama

Prerequisites:
  - Ollama must be installed and running (https://ollama.com/download)
  - Python packages: pip install -r requirements.txt
"""

import os
import sys
import subprocess
import shutil

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
MODELS_DIR = os.path.join(PROJECT_ROOT, "models")

# --- Configuration ---
HF_REPO_ID = "DIZ-23/smartstudy-model"  # <-- UPDATE THIS after uploading
GGUF_FILENAME = "phi-3.5-mini-instruct.Q4_K_M-001.gguf"
GGUF_PATH = os.path.join(MODELS_DIR, GGUF_FILENAME)


def check_ollama():
    """Verify Ollama is installed and reachable."""
    if not shutil.which("ollama"):
        print("ERROR: Ollama is not installed or not in PATH.")
        print("       Download it from: https://ollama.com/download")
        sys.exit(1)

    # Quick connectivity check
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            print("WARNING: 'ollama list' failed. Make sure Ollama is running.")
            print(f"         Error: {result.stderr.strip()}")
            sys.exit(1)
    except subprocess.TimeoutExpired:
        print("ERROR: Ollama is not responding. Please start the Ollama application.")
        sys.exit(1)


def download_model():
    """Download the GGUF file from HuggingFace if not already present."""
    if os.path.exists(GGUF_PATH):
        size_gb = os.path.getsize(GGUF_PATH) / (1024 ** 3)
        print(f"Model already exists: {GGUF_PATH} ({size_gb:.1f} GB)")
        return

    print(f"Downloading model from HuggingFace: {HF_REPO_ID}...")
    print("This is a ~2.2 GB download. Please wait...\n")

    try:
        from huggingface_hub import hf_hub_download

        hf_hub_download(
            repo_id=HF_REPO_ID,
            filename=GGUF_FILENAME,
            local_dir=MODELS_DIR,
            local_dir_use_symlinks=False,
        )
        print(f"\nDownload complete: {GGUF_PATH}")

    except ImportError:
        print("ERROR: 'huggingface_hub' package not installed.")
        print("       Run: pip install huggingface_hub")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR downloading model: {e}")
        sys.exit(1)


def create_ollama_model(model_name, modelfile_name):
    """Create an Ollama model from a Modelfile."""
    modelfile_path = os.path.join(MODELS_DIR, modelfile_name)

    if not os.path.exists(modelfile_path):
        print(f"WARNING: {modelfile_path} not found, skipping '{model_name}'.")
        return

    print(f"\nCreating Ollama model '{model_name}' from {modelfile_name}...")
    print("This may take a minute on first run...\n")

    result = subprocess.run(
        ["ollama", "create", model_name, "-f", modelfile_path],
        capture_output=True, text=True, timeout=300
    )

    if result.returncode == 0:
        print(f"  Model '{model_name}' created successfully!")
    else:
        print(f"  ERROR creating '{model_name}': {result.stderr.strip()}")
        sys.exit(1)


def main():
    print("=" * 60)
    print("  SmartStudy AI — Model Setup")
    print("=" * 60)
    print()

    # Step 1: Check Ollama
    print("[1/3] Checking Ollama installation...")
    check_ollama()
    print("  Ollama is ready.\n")

    # Step 2: Download model
    print("[2/3] Checking model file...")
    download_model()

    # Step 3: Register with Ollama
    print("[3/3] Registering models with Ollama...")
    create_ollama_model("smartstudy_ai", "Modelfile")
    create_ollama_model("kdu_advisor", "Modelfile_llama")

    print()
    print("=" * 60)
    print("  Setup complete! You can now run the app:")
    print("    streamlit run app/app.py")
    print("=" * 60)


if __name__ == "__main__":
    main()
