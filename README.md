# SmartStudy AI — KDU Academic Advisor

An AI-powered study planner for BSc (Hons) IT students at KDU. Uses a fine-tuned Phi-3.5 Mini model (via Ollama) to generate personalized study plans and academic advice.

---

## Prerequisites

| Tool | Version | Download |
|------|---------|----------|
| **Python** | 3.10+ | [python.org](https://www.python.org/downloads/) |
| **Ollama** | 0.34+ | [ollama.com/download](https://ollama.com/download) |
| **Git** | any | [git-scm.com](https://git-scm.com/) |

> [!IMPORTANT]
> **Ollama must be installed and running** before you set up the model.
> On Windows, just open the Ollama app. On Mac/Linux, run `ollama serve`.

---

## Quick Start (for team members)

```bash
# 1. Clone the repo
git clone https://github.com/DIZ-23/Smart_Study.git
cd Smart_Study

# 2. Create a virtual environment
python -m venv .venv

# Windows
.venv\Scripts\activate

# Mac/Linux
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Download the model & register with Ollama (one-time, ~2.2 GB download)
python scripts/setup_model.py

# 5. Run the app
streamlit run app/app.py
```

That's it! The setup script handles downloading the model and configuring Ollama automatically.

---

## Project Structure

```
Smart_Study/
├── app/
│   └── app.py                 # Main Streamlit application
├── data/
│   ├── kdu_student_dataset.csv
│   ├── student_performance_dataset.csv
│   └── student_training_data.jsonl
├── models/
│   ├── Modelfile              # Ollama config for smartstudy_ai (Phi-3.5)
│   ├── Modelfile_llama        # Ollama config for kdu_advisor (Llama 3.2)
│   └── *.gguf                 # Model weights (NOT in git — downloaded via setup script)
├── scripts/
│   ├── setup_model.py         # One-click model download & registration
│   ├── guardrails.py          # Academic rule checks
│   ├── convert_to_jsonl.py    # Dataset conversion utility
│   └── ...
├── .streamlit/
│   └── config.toml            # Streamlit theme config
├── requirements.txt
└── README.md
```

---

## How the Model Works

The app uses **two Ollama models**:

| Model Name | Base | Purpose |
|-------------|------|---------|
| `smartstudy_ai` | Phi-3.5 Mini (GGUF) | Study plan generation, performance prediction |
| `kdu_advisor` | Llama 3.2 (pulled from Ollama) | Follow-up chat, Q&A |

The Phi-3.5 model is a ~2.2 GB quantized GGUF file hosted on HuggingFace. The `setup_model.py` script downloads it and registers both models with Ollama.

---

## Troubleshooting

### "Connection refused" or "Ollama not responding"
Make sure Ollama is running:
- **Windows**: Open the Ollama application from the Start menu
- **Mac/Linux**: Run `ollama serve` in a terminal

### Model download fails
If the automatic download fails, you can manually download the model:
1. Go to: `https://huggingface.co/YOUR_HF_USERNAME/smartstudy-model`
2. Download `phi-3.5-mini-instruct.Q4_K_M-001.gguf`
3. Place it in the `models/` folder
4. Run `python scripts/setup_model.py` again (it will skip the download and just register)

### "Model not found" when running the app
Run the setup script again:
```bash
python scripts/setup_model.py
```

---

## Tech Stack

- **Frontend**: Streamlit
- **LLM Runtime**: Ollama
- **Models**: Phi-3.5 Mini (GGUF), Llama 3.2
- **Data**: Pandas

---

## License

This project is for educational purposes at KDU.
