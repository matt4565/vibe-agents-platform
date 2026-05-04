# 🚀 VibeAgents Platform
**Your Virtual AI Coworker Team for Vibe Coding**

A collaborative multi-agent chatbot platform where **Planner**, **Build Prompt Writer**, and **UI Designer** agents work together like a real startup team. They discuss your project idea step-by-step — frank, harsh, teacher-level feedback — produce detailed plans, elite build prompts (with smart tool/library choices), and stunning UI/UX specs.

**v2.1 (May 2026)**: 
- Real **CrewAI** agents with tools, memory & delegation
- **Smart Routing + Quick Presets** for latest models:
  - **Grok 4.2 Reasoning** (internal 4-agent debate)
  - **Grok 4.1 Fast** (cheap & fast)
  - **Gemini 3.1 Pro + Nano Banana** (best vision)
  - **Smart Mode** (recommended): Nano Banana (vision) → Grok 4.1 Fast (rounds) → Gemini 3.1 Pro (synthesis)

Inspired by Gemini (UI vision) + ChatGPT (planning & prompting) but as autonomous coworkers that talk to each other.

## ✨ Key Features
- **Smart Routing + Latest Models (v2.1)**: One-click presets for Grok 4.2, Grok 4.1 Fast, Gemini 3.1 Pro + Nano Banana. Smart Mode automatically uses the best model for each phase (vision / discussion / synthesis).
- **Real CrewAI Agents**: Planner, BuildPromptWriter & UIDesigner are first-class CrewAI agents with **tools** (playbook reader), **memory**, and **delegation** capability.
- **Multi-Agent Discussion**: Agents converse in rounds with harsh, teacher-level feedback. They call each other out and hand off naturally.
- **Playbooks & Assets**: Each agent has dedicated playbooks they read via tools for consistent "vibe coding" philosophy.
- **Structured Outputs**:
  - 📋 Comprehensive Project Plan (scope, tech decisions, risks, timeline)
  - 🛠️ Production-Ready Build Prompts (copy-paste to Cursor/Claude — includes exact tool choices + "Override if...")
  - 🎨 Detailed UI/UX Design System (components, flows, palettes, accessibility, micro-interactions + mockup prompts)
- **Vibe Coder Assistant**: After collaboration, chat with the combined "VibeCoder" brain (full context + vision loaded).
- **Zero RAG Overhead**: No external vector DB needed — playbooks are small and injected directly. (As you requested: "xcollection for rag part no")

## 🛠️ How Many APIs Do You Need?
**Only 1 LLM API key** (OpenAI-compatible):
- **Recommended**: 
  - OpenAI (gpt-4o or gpt-4o-mini) — best quality + vision
  - Groq (llama-3.1-70b or mixtral) — blazing fast & cheap
  - xAI Grok (grok-2 or beta) — via OpenAI-compatible endpoint if available
  - Anthropic Claude 3.5/Opus — excellent reasoning (use via OpenAI proxy or direct if you extend)
- Set `OPENAI_API_KEY` + optional `OPENAI_BASE_URL` (e.g. `https://api.groq.com/openai/v1` for Groq)
- Temperature: 0.6–0.8 for creative but structured responses
- No other APIs required. Image generation for mockups can be added later (e.g. via Replicate or Fal.ai).

## 🚀 Quick Start (Local)
1. Clone or download this folder
2. `cd vibe-agents-platform`
3. `python -m venv venv && source venv/bin/activate` (or Windows equivalent)
4. `pip install -r requirements.txt`  (includes CrewAI + vision deps)
5. `cp .env.example .env` and edit with your API key (gpt-4o recommended)
6. `streamlit run app.py`
7. Open browser → enter your project idea (e.g. "A vibe-based habit tracker app with social feed and AI insights, modern minimalist dark theme") 
8. Upload any reference screenshots or playbook overrides if you have
9. Hit **Launch Agent Collaboration** → watch the team argue, plan, and deliver!

## 📁 Project Structure
```
vibe-agents-platform/
├── app.py                 # Main Streamlit UI + agent orchestration
├── requirements.txt
├── .env.example
├── README.md
├── playbooks/
│   ├── company_vision.md      # Core "vibe coding" philosophy
│   ├── planner_playbook.md    # How Planner thinks & critiques
│   ├── prompt_writer_playbook.md
│   └── ui_designer_playbook.md
└── assets/                    # Default images or future agent avatars
```

## 🎯 How the Agents Work Together (Teacher Mode)
- **Planner 👔**: Starts every round. Brutally honest feasibility check, breaks scope, asks clarifying questions (shown to you), defines milestones.
- **BuildPromptWriter ✍️**: Turns plans into **god-tier structured prompts** for any coder LLM. Recommends specific tools/libraries with "why this vibe fits" reasoning. You get dropdown/editable choices in output.
- **UIDesigner 🎨**: Like Gemini on steroids — pixel-perfect descriptions, Tailwind classes, Framer Motion suggestions, user journey maps, "this button feels dead, make it breathe with this animation".
- They reference playbooks constantly and call each other out: "Planner, your timeline is too optimistic — UI Designer, the 3D elements will kill mobile perf!"

## 💡 Example Use Cases
- "Build a SaaS landing page with waitlist and demo video embed, playful startup vibe"
- "Internal tool for designers to generate prompt variations, clean enterprise UI"
- "Mobile-first fitness app with AI form checker, cyberpunk neon vibe"

## 🔧 Customization
- Edit playbooks/ to match **your** company voice
- Add more agents (e.g. BackendDev, QA) by extending the turn cycle in app.py
- Advanced: Switch to CrewAI for true tool-using delegation (PRs welcome)
- Vision: Upload real screenshots — code already prepared for gpt-4o vision messages

## ❓ FAQ
**Q: Can agents really "talk" to each other?**  
A: Yes — shared conversation history. Each response is conditioned on everything previous + playbooks.

**Q: Will it generate actual code?**  
A: The Build Prompts are optimized so you copy them into Cursor/Claude and get production code instantly. The platform itself focuses on planning + prompting (the hard part).

**Q: Harsh mode too harsh?**  
A: Toggle "Nice Mode" in sidebar (raises temperature + softer system prompt). Default = real startup co-founder energy.

**Q: My playbooks?**  
A: Drop your .md files in playbooks/ or upload in the UI — they get injected automatically.

Built with ❤️ for vibe coders who want coworkers that actually ship.

Now go launch your idea! 🚀
