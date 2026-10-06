# Project Change Log & History — SmartStudy AI (KDU)

This document tracks all project setup actions, code modifications, UI/UX overhauls, bug fixes, and feature additions made to the **SmartStudy AI — KDU Academic Advisor** application.

---

## 📌 Change Log Index
- [2026-10-06 — v2.2.1: Professional Iconography & Emoji Cleanup](#2026-10-06--v221-professional-iconography--emoji-cleanup)
- [2026-10-06 — v2.2.0: Advanced Visual Effects & Premium Micro-Animations](#2026-10-06--v220-advanced-visual-effects--premium-micro-animations)
- [2026-10-06 — v2.1.0: Complete UI/UX Overhaul & Interactive Features](#2026-10-06--v210-complete-uiux-overhaul--interactive-features)
- [2026-10-06 — v2.0.0: Initial Project Clone, Environment Setup & Model Configuration](#2026-10-06--v200-initial-project-clone-environment-setup--model-configuration)

---

## [2026-10-06 — v2.2.1: Professional Iconography & Emoji Cleanup]

### 🎯 Purpose
Replace casual emoji icons across all headers, cards, buttons, tabs, and alerts with clean typography and sleek inline SVG vector icons for a professional, academic aesthetic.

### 📂 Files Modified
- [`app/app.py`](file:///C:/Users/user/.gemini/antigravity-ide/scratch/Smart-Study/app/app.py) — Removed casual emojis from 35+ UI elements, replaced key icons with SVG vectors
- [`CHANGELOG.md`](file:///C:/Users/user/.gemini/antigravity-ide/scratch/Smart-Study/CHANGELOG.md) — Added this v2.2.1 entry

### 📝 Summary of Changes
- **Header & Sidebar**: Replaced header emoji logo with a sleek SVG academic cap/layer icon badge and updated sidebar title to clean typography.
- **Buttons & Banners**: Removed emojis from sidebar action button, quick-prompt chips, success banners, warning banners, and download PDF button.
- **Navigation Tabs**: Cleaned tab titles (`Study Roadmap & Tasks`, `Exam Strategy & Tips`, `Curated Resources & Past Papers`, `Ask Academic Advisor`).
- **Cards & Section Labels**: Stripped emojis from overview cards, progress completion cards, phase labels, tips card, and welcome dashboard modules.
- **Resource Cards**: Replaced casual emoji placeholders with crisp vector SVG icons (video camera, document page, library archive).
- **Backend Integrity**: Preserved backend `sanitize_llm_output` parsing string rules so LLM task extraction remains fully functional.

---



### 🎯 Purpose
Elevate the visual experience from polished to **premium-tier** with 18+ new CSS animations, ambient effects, and interactive micro-interactions. Transform the UI from a functional dark-mode dashboard into a living, breathing interface with depth, motion, and delight.

### 📂 Files Modified
- [`app/app.py`](file:///C:/Users/user/.gemini/antigravity-ide/scratch/Smart-Study/app/app.py) — Added ~340 lines of new CSS animations + separate ambient injection block
- [`CHANGELOG.md`](file:///C:/Users/user/.gemini/antigravity-ide/scratch/Smart-Study/CHANGELOG.md) — Added this v2.2.0 entry

### 📝 Summary of Changes

#### 1. Ambient Background & Atmosphere
- **Third Floating Orb (Center Mesh)**: Added a violet/amber gradient orb positioned center-screen with a 25s looping `floatOrb3` animation including rotation, creating a tri-point aurora mesh with the existing top-left and bottom-right orbs.
- **Ambient Light Sweep**: A subtle indigo gradient silently sweeps across the main content area every 15 seconds, simulating theatrical stage lighting.
- **Sparkle Particles in Welcome Hero**: 8 tiny CSS radial-gradient particles (indigo, cyan, violet, amber, green) float gently inside the hero banner with a 12s breathe animation.

#### 2. Entrance & Stagger Animations
- **Feature Box Cards**: Staggered `fadeInUp` entrance (0.1s, 0.25s, 0.4s delay per card).
- **Step Cards**: Staggered `fadeInLeft` entrance (0.15s, 0.3s, 0.45s delay).
- **Metric Pills**: Staggered `scaleIn` pop entrance (0.05s–0.35s delay per pill).
- **Phase Cards**: `slideUp` entrance animation.
- **Resource Cards**: Staggered `fadeInUp` per column.
- **Concept Tags**: `tagPop` animation (scale from 0.7 → 1.08 → 1.0) with staggered delays per tag.
- **Chat Messages**: `fadeInUp` on each new message bubble.
- **Quick Prompt Chips**: Staggered float-in animation.
- **Success Banner**: `celebratePop` scale bounce (0.92 → 1.03 → 1.0) combined with `fadeInSlide`.

#### 3. Interactive Hover Effects
- **Glowing Animated Gradient Border on Phase Cards**: On hover, a hidden `::before` pseudo-element reveals a 4-color animated gradient border (400% background-size, 8s cycle) creating a "breathing neon outline" effect.
- **Parallax Hover Tilt on Quick-Start Module Cards**: On hover, cards undergo a subtle 3D tilt (`rotateY(-2deg) rotateX(1.5deg)`) with perspective preserved, adding a premium card-game feel.
- **Progress Card Glow**: Hover reveals an indigo box-shadow glow and border accent shift.
- **Tooltip Help Icon Glow**: Sidebar `?` help icons gain a drop-shadow glow and 15% scale bump on hover.

#### 4. Button & Input Enhancements
- **Rainbow Gradient Shimmer on Generate Button**: Sidebar CTA now cycles through a 5-stop gradient (indigo → violet → cyan → indigo → deep-indigo) with 300% background-size and a 6s `rainbowShift` animation.
- **Button Ripple on Click**: All buttons gain a CSS-only ripple effect: a circular white flash radiates from center on `active` state.
- **Download Button Bounce**: A gentle 4-step bounce animation on hover.
- **Focus Ring Glow**: All inputs, textareas, and select dropdowns gain a dual-ring indigo glow (`box-shadow: 0 0 0 2px ... + 0 0 16px ...`) on focus.

#### 5. Decorative & Polish
- **Neon Glow Dividers**: All `<hr>` elements replaced with a multi-stop gradient line (transparent → indigo → cyan → violet → transparent) with a pulsing `glowPulse` box-shadow.
- **Animated Gradient Text on Welcome Title**: The `welcome-title` uses a 5-stop gradient with 300% background-size animating `gradientText` over 8s, creating a shimmering rainbow text effect.
- **Animated Number Pulse on Metric Values**: Values fade in with blur, overshoot scale, then settle (countPulse animation).
- **Hover Glow Underline on Tabs**: Inactive tabs gain a gradient underline that expands from center to 70% width on hover.
- **Animated Link Underlines**: All `<a>` tags gain an expanding gradient underline on hover.
- **Checkbox Completion Glow**: Checked checkboxes turn green-tinted with a left-border accent.
- **Sidebar Bottom Gradient**: Sidebar has a subtle bottom gradient fade.
- **Progress Bar Shine**: Periodic brightness pulse on the progress bar fill.
- **Live Dot Breathe**: GPU status dot combines pulse + brightness breathe animation.
- **Smooth Scrollbar**: Scrollbar thumb gains a hover glow effect.
- **Version Badge**: Updated from `KDU Edition v2.1` → `KDU Edition v2.2`.

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
