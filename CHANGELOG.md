# Project Change Log & History — SmartStudy AI (KDU)

This document tracks all project setup actions, code modifications, UI/UX overhauls, bug fixes, and feature additions made to the **SmartStudy AI — KDU Academic Advisor** application.

---

## 📌 Change Log Index
- [2026-10-06 — v2.1.0: Complete UI/UX Overhaul & Interactive Features](#2026-10-06--v210-complete-uiux-overhaul--interactive-features)
- [2026-10-06 — v2.0.0: Initial Project Clone, Environment Setup & Model Configuration](#2026-10-06--v200-initial-project-clone-environment-setup--model-configuration)

---

## [2026-10-06 — v2.1.0: Complete UI/UX Overhaul & Interactive Features]

### 🎯 Purpose
Modernize the user interface, eliminate the empty-state first view, fix glaring dark-mode contrast issues, group the 24 KDU BSc IT modules by semester, and provide an interactive, gamified study experience.

### 📂 Files Modified
- [`app/app.py`](file:///C:/Users/user/.gemini/antigravity-ide/scratch/Smart-Study/app/app.py)
- [`.streamlit/config.toml`](file:///C:/Users/user/.gemini/antigravity-ide/scratch/Smart-Study/.streamlit/config.toml)
- [`CHANGELOG.md`](file:///C:/Users/user/.gemini/antigravity-ide/scratch/Smart-Study/CHANGELOG.md) *(Created)*

### 📝 Summary of Changes

#### 1. Theme & Design System Upgrade
- **Dark Mode Palette**: Configured deep obsidian theme (`#0c0a17` base, `#151226` card background, `#6366f1` primary indigo accent, `#38bdf8` sky cyan, `#22c55e` emerald, `#f59e0b` amber).
- **Typography**: Integrated *Plus Jakarta Sans* and *Inter* fonts with clear typographic hierarchy.
- **Glassmorphism**: Added `backdrop-filter: blur(16px)` with subtle gradient borders (`rgba(255, 255, 255, 0.08)`) and hover elevation shadows.
- **Fixed Alert Banners**: Replaced high-contrast white-background alert boxes (`#f0fdf4` / `#fef2f2`) with dark-mode glassmorphic cards with glowing border accents.

#### 2. Welcome Dashboard (Empty State Solution)
- **Problem Solved**: First-time users previously encountered an 85% blank main canvas with all controls hidden in the sidebar.
- **Solution**: Implemented an informative landing dashboard featuring:
  - Welcome Hero Banner highlighting the KDU BSc IT advisory capabilities.
  - 3 Highlight Cards: 24 Module Syllabus Mapping, Adaptive Timelines, and Comprehensive Study Packs.
  - 3-Step Visual Getting Started Guide.
  - Quick-Select Popular Module Cards (*OOP, DSA, Networks I, Operating Systems*) that pre-select courses in one click.

#### 3. Academic Semester Filtering
- **Problem Solved**: A flat dropdown containing 24 modules with lengthy course codes was cumbersome to navigate.
- **Solution**: Added a Semester Filter (`Year 1 • Sem 1`, `Year 1 • Sem 2`, `Year 2 • Sem 1`, etc.) that dynamically filters the Target Subject list down to the 3–4 subjects relevant to that specific semester.

#### 4. Tabbed Results Layout
- **Problem Solved**: Generated results created an excessively long vertical scroll page.
- **Solution**: Organized output into 4 dedicated tabs:
  - **`📅 Study Roadmap & Tasks`**: Strategy Overview card, dynamic task progress bar, and phase breakdowns.
  - **`💡 Exam Strategy & Tips`**: High-scoring tips, common pitfalls, and the night-before checklist.
  - **`📚 Curated Resources & Past Papers`**: Video lectures, documentation, direct link to search the KDU Library archive, and PDF download button.
  - **`💬 Ask Academic Advisor`**: Follow-up chat interface with interactive Quick Prompt suggestion chips.

#### 5. Interactive Roadmap Checklist & Progress Tracking
- Converted static text action tasks into interactive checkboxes.
- Added live progress tracking displaying the number of completed tasks and overall percentage (e.g., `5 of 16 Action Steps Completed (31%)`).

---

## [2026-10-06 — v2.0.0: Initial Project Clone, Environment Setup & Model Configuration]

### 🎯 Purpose
Prepare and initialize the SmartStudy AI repository according to instructions in [`README.md`](file:///C:/Users/user/.gemini/antigravity-ide/scratch/Smart-Study/README.md).

### 📂 Files & Directories Created / Modified
- Repository cloned into [`C:\Users\user\.gemini\antigravity-ide\scratch\Smart-Study`](file:///C:/Users/user/.gemini/antigravity-ide/scratch/Smart-Study)
- Virtual Environment: [`.venv`](file:///C:/Users/user/.gemini/antigravity-ide/scratch/Smart-Study/.venv)
- Downloaded Model: [`models/phi-3.5-mini-instruct.Q4_K_M-001.gguf`](file:///C:/Users/user/.gemini/antigravity-ide/scratch/Smart-Study/models/phi-3.5-mini-instruct.Q4_K_M-001.gguf) (~2.2 GB)

### 📝 Summary of Actions
1. **Repository Setup**:
   - Cloned `https://github.com/SAF-Samod/Smart-Study.git`.
2. **Environment & Dependencies**:
   - Created Python 3.11 virtual environment (`.venv`).
   - Installed all required packages from `requirements.txt` (`streamlit>=1.62.0`, `ollama>=0.6.2`, `fpdf2>=2.8.8`, `pandas>=3.0.5`, `huggingface_hub>=0.30.0`).
3. **Ollama Installation & Startup**:
   - Installed Ollama `v0.35.1` via `winget`.
   - Launched Ollama background service with NVIDIA GeForce RTX 4060 GPU acceleration enabled.
4. **Model Download & Ollama Registration**:
   - Executed [`scripts/setup_model.py`](file:///C:/Users/user/.gemini/antigravity-ide/scratch/Smart-Study/scripts/setup_model.py).
   - Downloaded quantized GGUF weights `phi-3.5-mini-instruct.Q4_K_M-001.gguf` from Hugging Face (`DIZ-23/smartstudy-model`).
   - Registered `smartstudy_ai:latest` in Ollama using [`models/Modelfile`](file:///C:/Users/user/.gemini/antigravity-ide/scratch/Smart-Study/models/Modelfile).
   - Registered `kdu_advisor:latest` (with `llama3.2` base model) in Ollama using [`models/Modelfile_llama`](file:///C:/Users/user/.gemini/antigravity-ide/scratch/Smart-Study/models/Modelfile_llama).
5. **Runtime Verification**:
   - Started and verified local Streamlit application on `http://localhost:8501`.

---

## 📋 Format for Future Changes

To add a new entry to this file, use the following template:

```markdown
## [YYYY-MM-DD — vX.Y.Z: Title of Change]

### 🎯 Purpose
Brief explanation of what problem this change solves or what feature it introduces.

### 📂 Files Modified
- [`path/to/file.ext`](file:///path/to/file.ext)

### 📝 Summary of Changes
- Bullet point description of each change.
- Technical considerations, new libraries, or architectural modifications.
```
