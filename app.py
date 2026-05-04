# v2.5.0 - Added Debug Section for easy troubleshooting
import streamlit as st
import os
from openai import OpenAI
from dotenv import load_dotenv
import json
from datetime import datetime
from PIL import Image
import base64
from io import BytesIO
import time
import traceback

# ============== CREWAI INTEGRATION ==============
from crewai import Agent, Task, Crew, Process, LLM
from crewai_tools import FileReadTool

# Load environment
load_dotenv()
st.set_page_config(page_title="VibeAgents • Virtual Coworkers", page_icon="🚀", layout="wide")

# ============== MULTI-PROVIDER CONFIG ==============
PROVIDERS = {
    "xAI Grok": {
        "emoji": "🧠",
        "base_url": "https://api.x.ai/v1",
        "api_placeholder": "xai-...",
        "models": [
            "grok-4.3",
            "grok-4.20-multi-agent-0309",
            "grok-4.20-0309-reasoning",
            "grok-4-1-fast-reasoning",
            "grok-4-1-fast-non-reasoning",
        ],
    },
    "Google Vertex AI": {
        "emoji": "🌐",
        "base_url": "https://us-central1-aiplatform.googleapis.com/v1/projects/YOUR_PROJECT_ID/locations/us-central1/publishers/google/models/",
        "api_placeholder": "AIza...",
        "help": "Using Google Gemini Enterprise / Agent Platform",
        "models": [
            "gemini-3.1-pro-preview",
            "gemini-3.1-flash-preview",
            "gemini-3.1-flash-lite-preview",
            "veo-3.1-lite-generate-preview",
        ],
    },
    "OpenAI": {
        "emoji": "🤖",
        "base_url": "https://api.openai.com/v1",
        "api_placeholder": "sk-...",
        "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"],
    },
    "Groq (Free)": {
        "emoji": "⚡",
        "base_url": "https://api.groq.com/openai/v1",
        "api_placeholder": "gsk_...",
        "models": ["llama-3.3-70b-versatile", "mixtral-8x7b-32768"],
    },
    "Anthropic": {
        "emoji": "🔮",
        "base_url": "https://api.anthropic.com/v1",
        "api_placeholder": "sk-ant-...",
        "models": ["claude-sonnet-4-20250514", "claude-3-5-haiku-20241022"],
    },
    "Custom": {
        "emoji": "🔧",
        "base_url": "",
        "api_placeholder": "your-api-key",
        "models": [],
    },
}

# Default per-agent config template
DEFAULT_AGENT_CONFIG = {
    "provider": "xAI Grok",
    "api_key": "",
    "base_url": "https://api.x.ai/v1",
    "model": "grok-4.3",
}

# Map agent keys to session_state config keys
AGENT_CONFIG_KEYS = {
    "Planner": "planner_config",
    "BuildPromptWriter": "writer_config",
    "UIDesigner": "designer_config",
}

def _resolve_provider_for_model(model: str) -> dict | None:
    """Find which PROVIDER owns a model name; return its config or None."""
    for prov_name, prov in PROVIDERS.items():
        if model in prov["models"]:
            return {"provider": prov_name, "base_url": prov["base_url"]}
    return None

def _validate_agent_config(agent_name: str, cfg: dict) -> dict:
    """Ensure model and base_url belong to the same provider.
    
    If the model belongs to a different provider than the base_url,
    fix the base_url to match the model's provider and show a warning.
    Returns the corrected config dict.
    """
    model = cfg.get("model", "")
    base_url = cfg.get("base_url", "")
    resolved = _resolve_provider_for_model(model)
    if resolved and resolved["base_url"] != base_url:
        st.warning(
            f"⚠️ **{agent_name}**: model `{model}` belongs to **{resolved['provider']}**, "
            f"but base_url points elsewhere. Auto-correcting to `{resolved['base_url'][:60]}…`"
        )
        cfg = {**cfg, "base_url": resolved["base_url"], "provider": resolved["provider"]}
    return cfg

def get_agent_config(agent_name: str) -> dict:
    """Return the per-agent config dict from session_state.
    
    Checks live widget keys first (so Team Overview stays current even
    before the user clicks Save), then falls back to the stored config.
    """
    key = AGENT_CONFIG_KEYS.get(agent_name, "planner_config")
    stored = st.session_state.get(key, DEFAULT_AGENT_CONFIG.copy())
    # Overlay live widget values if they exist (user changed dropdowns but hasn't saved yet)
    live = stored.copy()
    if f"{key}_prov" in st.session_state:
        live["provider"] = st.session_state[f"{key}_prov"]
    if f"{key}_model" in st.session_state:
        live["model"] = st.session_state[f"{key}_model"]
    if f"{key}_url" in st.session_state:
        live["base_url"] = st.session_state[f"{key}_url"]
    if f"{key}_key" in st.session_state:
        live["api_key"] = st.session_state[f"{key}_key"]
    return live

def get_active_config():
    """Backwards-compat: return planner config as the 'active' global config."""
    return get_agent_config("Planner")

def _team_summary_text() -> str:
    """Build a short summary like '3 agents • 2 xAI • 1 Vertex'."""
    provider_counts: dict[str, int] = {}
    for agent_name in AGENT_CONFIG_KEYS:
        cfg = get_agent_config(agent_name)
        p = cfg.get("provider", "xAI Grok")
        provider_counts[p] = provider_counts.get(p, 0) + 1
    parts = [f"{v} {k}" for k, v in provider_counts.items()]
    return f"3 agents configured • {' • '.join(parts)}"

# ============== CONFIG & HELPERS ==============
AGENTS = {
    "Planner": {
        "emoji": "👔",
        "color": "#FF6B6B",
        "role": "Senior Product Planner & Brutal Mentor",
        "backstory": "You are a 15+ year startup veteran who has killed more bad ideas than most people ship. You speak with tough love — frank, harsh, but always constructive like a teacher who wants their students to succeed. Never sugarcoat. Every response must teach or destroy mediocrity."
    },
    "BuildPromptWriter": {
        "emoji": "✍️",
        "color": "#4ECDC4",
        "role": "Master Prompt Engineer & Vibe Coder Architect",
        "backstory": "You are the world's best prompt engineer. You turn team chaos into god-tier, copy-paste prompts that make Claude, Cursor, or Gemini output production code on the first try. Obsessed with structure, tool choices, and matching the exact emotional vibe of the product."
    },
    "UIDesigner": {
        "emoji": "🎨",
        "color": "#45B7D1",
        "role": "World-Class UI/UX Designer (Gemini-level vision)",
        "backstory": "You see finished interfaces in your mind before code exists. 2026 design trends expert. You are poetic but precise, brutally honest about what feels dead vs alive. Every pixel and interaction must serve the soul of the product."
    }
}

def get_client():
    cfg = get_active_config()
    api_key = cfg.get("api_key", "")
    base_url = cfg.get("base_url", "")
    provider = cfg.get("provider", "xAI Grok")
    if not base_url:
        base_url = PROVIDERS.get(provider, {}).get("base_url", "https://api.x.ai/v1")
    if not api_key:
        st.error(f"⚠️ No API key for **{provider}**. Configure it in the sidebar and click Save!")
        st.stop()
    return OpenAI(api_key=api_key, base_url=base_url)

def load_playbooks():
    playbooks = {}
    pb_dir = "playbooks"
    for fname in ["company_vision.md", "planner_playbook.md", "prompt_writer_playbook.md", "ui_designer_playbook.md"]:
        path = os.path.join(pb_dir, fname)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                playbooks[fname.replace(".md", "")] = f.read()
        else:
            playbooks[fname.replace(".md", "")] = "Playbook not found."
    return playbooks

def get_rich_visual_description(uploaded_files, captions, client):
    """Use gpt-4o vision to deeply analyze all screenshots for the agents"""
    if not uploaded_files:
        return "No screenshots provided by user."
    
    descriptions = []
    for i, (file, cap) in enumerate(zip(uploaded_files, captions)):
        try:
            img = Image.open(file)
            buffered = BytesIO()
            img.save(buffered, format="PNG")
            img_base64 = base64.b64encode(buffered.getvalue()).decode()
            
            vision_prompt = f"""You are a world-class UI/UX researcher and product planner.
Analyze this screenshot in extreme detail for a team of AI agents building a product.

Caption from user: {cap}

Provide a rich, structured analysis covering:
- Overall layout & visual hierarchy
- Color palette, typography, spacing, and "vibe" (playful, corporate, dark, minimalist, etc.)
- Key components (buttons, forms, cards, navigation, etc.) and their states
- Any text content, CTAs, or user flows visible
- Potential UX issues or strengths you notice
- How this screenshot relates to the product idea (if obvious)
- Specific recommendations for improvement or inspiration

Be precise and visual — this will be read by Planner, Prompt Writer, and UI Designer agents."""

            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are an expert visual analyst."},
                    {"role": "user", "content": [
                        {"type": "text", "text": vision_prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_base64}"}}
                    ]}
                ],
                max_tokens=800,
                temperature=0.4
            )
            desc = response.choices[0].message.content.strip()
            descriptions.append(f"**Screenshot {i+1} ({cap})**:\n{desc}")
        except Exception as e:
            descriptions.append(f"**Screenshot {i+1}**: Could not analyze ({str(e)})")
    
    return "\n\n".join(descriptions)

# ============== CREWAI AGENT FACTORY ==============
def _make_llm(agent_name: str, agent_configs: dict | None = None) -> LLM:
    """Create an LLM instance using per-agent config (or session_state fallback).
    
    Never falls back to OpenAI env vars — each agent must have its own
    api_key and base_url from its provider config.
    """
    if agent_configs and agent_name in agent_configs:
        c = agent_configs[agent_name]
    else:
        c = get_agent_config(agent_name)
    # Validate: ensure model + base_url belong to the same provider
    c = _validate_agent_config(agent_name, c)
    api_key = c.get("api_key", "")
    if not api_key:
        st.warning(f"⚠️ **{agent_name}** has no API key for {c.get('provider', 'unknown')}. It will likely fail.")
    return LLM(
        model=c.get("model", "grok-4.3"),
        api_key=api_key,
        base_url=c.get("base_url", "https://api.x.ai/v1"),
        temperature=0.65,
    )

def create_vibe_crewai_agents(playbooks: dict, agent_configs: dict | None = None,
                              model: str = "", api_key: str = "", base_url: str = ""):
    """Create real CrewAI agents with per-agent LLM configs.
    
    If agent_configs is provided (dict mapping agent_name -> config dict),
    each agent gets its own LLM.  Falls back to a shared LLM for backward compat.
    """
    
    # Build per-agent LLMs
    if agent_configs:
        llm_planner = _make_llm("Planner", agent_configs)
        llm_writer  = _make_llm("BuildPromptWriter", agent_configs)
        llm_designer = _make_llm("UIDesigner", agent_configs)
    else:
        shared = LLM(model=model, api_key=api_key, base_url=base_url, temperature=0.65)
        llm_planner = llm_writer = llm_designer = shared
    
    playbook_tools = [
        FileReadTool(file_path="playbooks/company_vision.md"),
        FileReadTool(file_path="playbooks/planner_playbook.md"),
        FileReadTool(file_path="playbooks/prompt_writer_playbook.md"),
        FileReadTool(file_path="playbooks/ui_designer_playbook.md"),
    ]
    
    planner = Agent(
        role=AGENTS["Planner"]["role"],
        goal="Lead brutally honest planning discussions. Expose vague ideas, define realistic MVP scope, ask hard clarifying questions, and force the team to ship something valuable fast. Reference playbooks constantly.",
        backstory=AGENTS["Planner"]["backstory"] + "\n\n" + playbooks.get("planner_playbook", ""),
        tools=playbook_tools,
        llm=llm_planner,
        memory=True,
        allow_delegation=True,
        verbose=False,
        max_iter=6,
        max_rpm=20
    )
    
    prompt_writer = Agent(
        role=AGENTS["BuildPromptWriter"]["role"],
        goal="Transform team decisions into elite, structured, copy-paste-ready build prompts with perfect tool choices, folder structure, coding standards, and vibe-matching instructions. Every prompt must feel alive and 95%+ first-try success rate.",
        backstory=AGENTS["BuildPromptWriter"]["backstory"] + "\n\n" + playbooks.get("prompt_writer_playbook", ""),
        tools=playbook_tools,
        llm=llm_writer,
        memory=True,
        allow_delegation=True,
        verbose=False,
        max_iter=6
    )
    
    ui_designer = Agent(
        role=AGENTS["UIDesigner"]["role"],
        goal="Design interfaces with soul. Validate every plan and prompt visually. Provide precise component specs, micro-interactions, color systems, accessibility, and ready-to-use image generation prompts. Call out anything that feels dead or over-engineered.",
        backstory=AGENTS["UIDesigner"]["backstory"] + "\n\n" + playbooks.get("ui_designer_playbook", ""),
        tools=playbook_tools,
        llm=llm_designer,
        memory=True,
        allow_delegation=True,
        verbose=False,
        max_iter=6
    )
    
    return {"Planner": planner, "BuildPromptWriter": prompt_writer, "UIDesigner": ui_designer}

def get_crewai_response(agent, agent_name: str, history: list, idea: str, visual_analysis: str, round_num: int):
    """Get response from a real CrewAI agent (with tools, memory, delegation)"""
    
    history_text = format_history_for_prompt(history)
    
    task_description = f"""You are participating in Round {round_num} of a team collaboration meeting.

PROJECT IDEA FROM USER:
{idea}

VISUAL ANALYSIS OF USER UPLOADED SCREENSHOTS (you can "see" these via this detailed analysis):
{visual_analysis}

PREVIOUS TEAM DISCUSSION (read carefully):
{history_text}

INSTRUCTIONS (stay 100% in character):
- Respond **exactly as {agent_name}**.
- Be **frank, harsh, and teacher-level** when needed. Praise good thinking loudly, destroy bad ideas with clear reasoning + alternatives.
- Reference the playbooks using your FileReadTool if you need specific guidelines.
- You have **memory** of previous turns and can **delegate** to teammates if it makes sense.
- Keep your response concise but rich (220-380 words).
- End with a clear hand-off, e.g. "BuildPromptWriter — structure the prompts now." or "UIDesigner — does this scope allow for the soul you're imagining?" or "Planner, am I missing any risks?"

Your response:"""

    task = Task(
        description=task_description,
        expected_output="The agent's in-character response (220-380 words) with clear hand-off at the end.",
        agent=agent,
    )
    
    mini_crew = Crew(
        agents=[agent],
        tasks=[task],
        process=Process.sequential,
        memory=True,
        verbose=False
    )
    
    try:
        result = mini_crew.kickoff()
        return str(result.raw).strip() if hasattr(result, 'raw') else str(result).strip()
    except Exception as e:
        return f"❌ CrewAI error for {agent_name}: {str(e)}. Falling back to direct LLM..."

def format_history_for_prompt(history):
    if not history:
        return "This is the very first turn. Start strong and set the tone."
    formatted = []
    for msg in history[-6:]:
        formatted.append(f"**{msg['agent']}** (Round {msg.get('round_num', '?')}): {msg['content'][:280]}...")
    return "\n\n".join(formatted)

def synthesize_final_outputs_crewai(agents: dict, history: list, idea: str, visual_analysis: str, playbooks: dict, model: str, api_key: str, base_url: str):
    """Use a real CrewAI task for high-quality final synthesis"""
    llm = LLM(model=model, api_key=api_key, base_url=base_url, temperature=0.5)
    
    synthesis_agent = agents["Planner"]
    
    task_desc = f"""You are the VibeAgents Chief Synthesizer (Planner leading final output).

PROJECT IDEA: {idea}

VISUAL CONTEXT: {visual_analysis[:1500]}

FULL DISCUSSION TRANSCRIPT (last 10 messages):
{json.dumps([{"agent": m["agent"], "content": m["content"][:200]} for m in history[-10:]], indent=2)}

COMPANY VISION & PLAYBOOKS (reference these):
{playbooks.get("company_vision", "")[:800]}

Now produce the **final structured deliverables** in clean, professional Markdown with these exact sections:

## 📋 PROJECT PLAN
(Brutal honest scope, MVP definition, tech decisions, risks, 4-week timeline, success metrics, open questions)

## 🛠️ BUILD PROMPTS (Ready to Copy-Paste)
3-5 elite prompts. Each must include: Vibe description, numbered requirements, **Tool Choices** section with recommendations + "Override if...", folder structure, success criteria.

## 🎨 UI/UX DESIGN SYSTEM & SPECS
Overall design language, color palette (hex + why), typography, key screens with component specs, 3 image generation prompts for mockups, accessibility notes.

## ❓ CLARIFYING QUESTIONS FOR USER
The 3-4 hardest questions the team still has.

## 🚀 NEXT STEPS
Immediate actions for the human (copy prompts, create repo, etc.)

Format beautifully with emojis and clear headings. Be as detailed and actionable as possible."""

    task = Task(
        description=task_desc,
        expected_output="Full Markdown synthesis with all 5 sections.",
        agent=synthesis_agent,
    )
    
    mini_crew = Crew(agents=[synthesis_agent], tasks=[task], process=Process.sequential, memory=True, verbose=False)
    try:
        result = mini_crew.kickoff()
        return str(result.raw).strip() if hasattr(result, 'raw') else str(result).strip()
    except Exception as e:
        return f"❌ Synthesis failed: {str(e)}"

# ============== SESSION STATE ==============
if "history" not in st.session_state:
    st.session_state.history = []
if "final_outputs" not in st.session_state:
    st.session_state.final_outputs = ""
if "playbooks" not in st.session_state:
    st.session_state.playbooks = load_playbooks()
if "visual_refs" not in st.session_state:
    st.session_state.visual_refs = ""
if "crewai_agents" not in st.session_state:
    st.session_state.crewai_agents = None
if "visual_analysis" not in st.session_state:
    st.session_state.visual_analysis = ""
# Per-agent configs
for _ak, _sk in AGENT_CONFIG_KEYS.items():
    if _sk not in st.session_state:
        st.session_state[_sk] = DEFAULT_AGENT_CONFIG.copy()

# ============== SIDEBAR ==============
with st.sidebar:
    st.title("⚙️ VibeAgents Control")

    # ── Team Overview — rendered via placeholder AFTER widgets below ────
    _team_overview_placeholder = st.empty()

    # ── Per-Agent LLM Configuration ──────────────────────
    st.subheader("🔑 Per-Agent LLM Config")
    provider_options = list(PROVIDERS.keys())

    def _on_provider_change(sk: str):
        """Callback: when provider dropdown changes, push the correct base_url into the URL widget."""
        new_prov = st.session_state.get(f"{sk}_prov", "xAI Grok")
        st.session_state[f"{sk}_url"] = PROVIDERS[new_prov]["base_url"]

    for agent_name, state_key in AGENT_CONFIG_KEYS.items():
        agent_info = AGENTS[agent_name]
        a_cfg = st.session_state[state_key]

        with st.expander(f"{agent_info['emoji']} **{agent_name}** — `{a_cfg.get('model','—')}`", expanded=False):
            # Provider (on_change pushes correct base_url)
            cur_prov = a_cfg.get("provider", "xAI Grok")
            prov_idx = provider_options.index(cur_prov) if cur_prov in provider_options else 0
            sel_prov = st.selectbox(
                "Provider",
                provider_options,
                index=prov_idx,
                format_func=lambda p: f"{PROVIDERS[p]['emoji']}  {p}",
                key=f"{state_key}_prov",
                on_change=_on_provider_change,
                args=(state_key,),
            )
            prov_info = PROVIDERS[sel_prov]

            # API Key
            st.text_input(
                "API Key",
                value=a_cfg.get("api_key", ""),
                type="password",
                placeholder=prov_info["api_placeholder"],
                key=f"{state_key}_key",
            )

            # Base URL — initialise widget key if not yet present
            url_wkey = f"{state_key}_url"
            if url_wkey not in st.session_state:
                st.session_state[url_wkey] = a_cfg.get("base_url", prov_info["base_url"])
            st.text_input(
                "Base URL",
                key=url_wkey,
                help="Auto-filled based on provider. Edit only if needed.",
            )

            # Model
            if sel_prov == "Custom":
                st.text_input(
                    "Model name",
                    value=a_cfg.get("model", ""),
                    placeholder="e.g. my-org/my-model",
                    key=f"{state_key}_model",
                )
            else:
                m_list = prov_info["models"]
                m_idx = m_list.index(a_cfg["model"]) if a_cfg.get("model") in m_list else 0
                st.selectbox(
                    "Model",
                    m_list,
                    index=m_idx,
                    key=f"{state_key}_model",
                )

            _prov_help = prov_info.get("help", "")
            _help_suffix = f" — {_prov_help}" if _prov_help else ""
            st.caption(f"🔗 {sel_prov} • {len(prov_info['models'])} models{_help_suffix}")

    # ── Save All / Load Saved ────────────────────────────
    col_s, col_l = st.columns(2)
    with col_s:
        if st.button("💾 Save All Configs", use_container_width=True, type="primary"):
            for agent_name, state_key in AGENT_CONFIG_KEYS.items():
                new_cfg = {
                    "provider": st.session_state.get(f"{state_key}_prov", "xAI Grok"),
                    "api_key": st.session_state.get(f"{state_key}_key", ""),
                    "base_url": st.session_state.get(f"{state_key}_url", ""),
                    "model": st.session_state.get(f"{state_key}_model", "grok-4.3"),
                }
                st.session_state[state_key] = new_cfg
            # Persist a backup copy
            st.session_state["saved_agent_configs"] = {
                sk: st.session_state[sk].copy() for sk in AGENT_CONFIG_KEYS.values()
            }
            st.toast("✅ All agent configurations saved!", icon="💾")
            st.rerun()
    with col_l:
        has_saved = "saved_agent_configs" in st.session_state
        if st.button("📂 Use Saved", use_container_width=True, disabled=not has_saved,
                      help="Load last saved configs" if has_saved else "No saved configs yet"):
            for sk, cfg_copy in st.session_state["saved_agent_configs"].items():
                st.session_state[sk] = cfg_copy.copy()
            st.toast("📂 Loaded saved configurations!", icon="✅")
            st.rerun()

    st.caption(f"_{_team_summary_text()}_")

    # ── Fill Team Overview placeholder (widgets above have now created their keys) ──
    _ov_models = []
    _ov_lines = []
    for _an in AGENT_CONFIG_KEYS:
        _cfg = get_agent_config(_an)
        _m = _cfg.get("model", "—")
        _ov_models.append(_m)
        _has_key = bool(_cfg.get("api_key"))
        _dot = "🟢" if _has_key else "🔴"
        _ov_lines.append(
            f'{_dot} {AGENTS[_an]["emoji"]} <b>{_an}</b> → '
            f'<code style="color:#7ee787;">{_m}</code>'
        )
    _ov_unique = list(dict.fromkeys(_ov_models))
    _team_overview_placeholder.markdown(
        f"""<div style="background:linear-gradient(135deg,#0d1117,#161b22);
        border:1px solid #30363d;border-radius:12px;padding:12px 14px;
        margin-bottom:14px;">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
          <span style="font-size:0.7rem;text-transform:uppercase;letter-spacing:1px;color:#8b949e;">Team Overview</span>
          <span style="font-size:0.7rem;color:#58a6ff;">3 Agents</span>
        </div>
        <div style="font-size:0.78rem;color:#c9d1d9;line-height:1.6;">
          {'<br/>'.join(_ov_lines)}
        </div>
        <div style="margin-top:8px;font-size:0.68rem;color:#8b949e;">
          Active models: {', '.join(_ov_unique)} · Est. ~$0.09/session
        </div>
        </div>""",
        unsafe_allow_html=True,
    )

    st.divider()

    # ── Temperature & Discussion Mode ─────────────────────
    temperature = st.slider("Creativity (Temperature)", 0.3, 1.0, 0.7, 0.1)

    discussion_mode = st.radio(
        "Discussion Mode",
        ["🔄 Open Discussion (Until Perfect)", "📐 Fixed Rounds"],
        index=0,
        help="Open Discussion lets agents refine until prompts are production-ready.",
        key="discussion_mode",
    )

    if discussion_mode.startswith("🔄"):
        max_rounds = st.slider("Max Rounds (safety limit)", 4, 12, 8, 1,
                               help="Hard stop — prevents infinite loops. Agents usually converge in 4–6 rounds.")
        num_rounds = max_rounds  # used as upper bound
        open_discussion = True
        st.markdown(
            """<div style="background:#0d1117;border:1px solid #238636;border-radius:8px;
            padding:10px 12px;font-size:0.78rem;color:#7ee787;margin-top:4px;">
            ♾️ Agents will keep refining until the <b>BuildPromptWriter</b> declares
            the prompts <i>production-ready</i> (max {max_r} rounds).
            </div>""".format(max_r=max_rounds),
            unsafe_allow_html=True,
        )
    else:
        num_rounds = st.slider("Discussion Rounds", 2, 5, 3, 1,
                               help="Each round = Planner → PromptWriter → UIDesigner")
        open_discussion = False

    st.divider()
    st.subheader("🎨 Nice Mode")
    nice_mode = st.toggle("Soften the harshness", value=False, help="Slightly higher temp + softer prompts")
    if nice_mode:
        temperature = min(0.95, temperature + 0.15)

    # ── Quick Presets (apply to ALL agents) ───────────────
    st.divider()
    st.subheader("🚀 Quick Presets")
    st.caption("Applies to **all 3 agents** at once. Override per-agent above.")

    def _apply_preset_all(provider, model, preset_key):
        """Set all agents to the same provider + model."""
        prov = PROVIDERS[provider]
        for sk in AGENT_CONFIG_KEYS.values():
            cur = st.session_state.get(sk, DEFAULT_AGENT_CONFIG.copy())
            cur["provider"] = provider
            cur["model"] = model
            cur["base_url"] = prov["base_url"]
            # Preserve existing api_key if same provider
            st.session_state[sk] = cur
        st.session_state["model_preset"] = preset_key

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🧠 Grok 4.2 Reasoning", use_container_width=True, help="All agents → grok-4.20-0309-reasoning"):
            _apply_preset_all("xAI Grok", "grok-4.20-0309-reasoning", "grok-4.2-reasoning")
            st.rerun()
        if st.button("⚡ Grok 4.1 Fast", use_container_width=True, help="All agents → grok-4-1-fast-reasoning"):
            _apply_preset_all("xAI Grok", "grok-4-1-fast-reasoning", "grok-4.1-fast")
            st.rerun()

    with col2:
        if st.button("👁️ Gemini 3.1 Pro", use_container_width=True, help="All agents → gemini-3.1-pro-preview"):
            _apply_preset_all("Google Vertex AI", "gemini-3.1-pro-preview", "gemini-3.1-vision")
            st.rerun()
        if st.button("✨ Smart Mode", use_container_width=True, type="primary", help="Auto-route: vision/rounds/synthesis"):
            st.session_state.model_preset = "smart"
            st.rerun()

    current_preset = st.session_state.get("model_preset", "smart")
    preset_labels = {
        "smart": "✨ Smart Mode (Auto-routing)",
        "grok-4.2-reasoning": "🧠 Grok 4.2 Reasoning",
        "grok-4.1-fast": "⚡ Grok 4.1 Fast",
        "gemini-3.1-vision": "👁️ Gemini 3.1 Pro",
    }
    st.caption(f"**Active Preset:** {preset_labels.get(current_preset, current_preset)}")

    st.divider()
    if st.button("🔄 Reset Everything", type="secondary"):
        for key in ["history", "final_outputs", "visual_refs", "visual_analysis", "crewai_agents"]:
            if key in st.session_state:
                st.session_state[key] = [] if key == "history" else ""
        for sk in AGENT_CONFIG_KEYS.values():
            st.session_state[sk] = DEFAULT_AGENT_CONFIG.copy()
        st.rerun()

    st.caption("VibeAgents v2.5.0 • Debug Tools • Per-Agent LLM • May 2026")

    # ── Debug & Logs ──────────────────────────────────────
    with st.expander("🔧 Debug & Logs (Advanced)", expanded=False):
        st.caption("Use this to debug errors. Copy and send to developer if needed.")

        show_traceback = st.toggle("Show Full Traceback", value=False, key="debug_traceback_toggle")

        # Last error
        last_err = st.session_state.get("_debug_last_error", "")
        last_tb = st.session_state.get("_debug_last_traceback", "")
        launch_status = st.session_state.get("_debug_launch_status", "No launch yet")

        st.markdown(f"**Last Launch Status:** `{launch_status}`")

        if last_err:
            st.error(f"**Last Error:** {last_err}")
            if show_traceback and last_tb:
                st.code(last_tb, language="python")
        else:
            st.success("No errors recorded.")

        # Per-agent configs
        st.markdown("---")
        st.markdown("**Current Per-Agent Configs:**")
        for _da, _dk in AGENT_CONFIG_KEYS.items():
            _dc = get_agent_config(_da)
            _masked_key = "***" + _dc.get("api_key", "")[-4:] if len(_dc.get("api_key", "")) > 4 else "(empty)"
            st.markdown(
                f"- **{_da}**: `{_dc.get('provider','?')}` · "
                f"`{_dc.get('model','?')}` · "
                f"key=`{_masked_key}` · "
                f"url=`{_dc.get('base_url','')[:55]}…`"
            )

        # Session state summary
        st.markdown("---")
        st.markdown("**Session State Summary:**")
        st.markdown(
            f"- History entries: `{len(st.session_state.get('history', []))}`\n"
            f"- Final outputs: `{'Yes' if st.session_state.get('final_outputs') else 'No'}`\n"
            f"- Visual analysis: `{'Yes' if st.session_state.get('visual_analysis') else 'No'}`\n"
            f"- Preset: `{st.session_state.get('model_preset', 'smart')}`\n"
            f"- Discussion mode: `{st.session_state.get('discussion_mode', '?')}`"
        )

        # Copy Debug Info
        debug_lines = [
            f"=== VibeAgents Debug Report ===",
            f"Timestamp: {datetime.now().isoformat()}",
            f"Launch Status: {launch_status}",
            f"Last Error: {last_err or 'None'}",
            f"",
        ]
        for _da, _dk in AGENT_CONFIG_KEYS.items():
            _dc = get_agent_config(_da)
            _masked = "***" + _dc.get("api_key", "")[-4:] if len(_dc.get("api_key", "")) > 4 else "(empty)"
            debug_lines.append(
                f"{_da}: provider={_dc.get('provider','?')} model={_dc.get('model','?')} "
                f"key={_masked} url={_dc.get('base_url','')}"
            )
        debug_lines += [
            f"",
            f"History: {len(st.session_state.get('history', []))} entries",
            f"Preset: {st.session_state.get('model_preset', 'smart')}",
        ]
        if show_traceback and last_tb:
            debug_lines += ["", "=== Full Traceback ===", last_tb]
        debug_text = "\n".join(debug_lines)

        st.code(debug_text, language="text")
        st.caption("☝️ Select all text above and copy, or use the copy icon.")

# ============== MAIN UI ==============
st.title("🚀 VibeAgents Platform")
st.caption("Your virtual AI coworkers (now with real CrewAI tools, memory & delegation)")

col1, col2 = st.columns([3, 1])
with col1:
    idea = st.text_area(
        "💡 Your Project Idea / Vibe Description",
        placeholder="A modern habit tracker with AI insights, social accountability feed, beautiful dark minimalist design, and streak celebrations that feel rewarding not gamified...",
        height=120,
        key="idea_input"
    )

with col2:
    st.write("**Visual References (now with vision)**")
    uploaded_files = st.file_uploader(
        "Upload screenshots / mockups",
        type=["png", "jpg", "jpeg", "webp"],
        accept_multiple_files=True,
        help="Agents will *see* these via gpt-4o vision analysis"
    )
    
    captions = []
    if uploaded_files:
        for i, file in enumerate(uploaded_files):
            col_img, col_cap = st.columns([1, 2])
            with col_img:
                img = Image.open(file)
                st.image(img, width=80)
            with col_cap:
                cap = st.text_input(f"Caption #{i+1}", value=f"Reference {i+1}: {file.name}", key=f"cap_{i}")
                captions.append(cap)
        st.session_state.visual_refs = " | ".join(captions)
        st.session_state.uploaded_images = uploaded_files
        st.session_state.uploaded_captions = captions
    else:
        st.session_state.visual_refs = ""
        if "uploaded_images" in st.session_state:
            del st.session_state.uploaded_images

if st.button("🚀 LAUNCH AGENT COLLABORATION (CrewAI + Vision)", type="primary", use_container_width=True, disabled=not idea.strip()):
  try:
    st.session_state.history = []
    st.session_state.final_outputs = ""
    st.session_state.visual_analysis = ""
    st.session_state["_debug_last_error"] = ""
    st.session_state["_debug_last_traceback"] = ""
    st.session_state["_debug_launch_status"] = "Running…"

    client = get_client()
    playbooks = st.session_state.playbooks
    preset = st.session_state.get("model_preset", "smart")
    
    # Build per-agent config dicts from session_state
    agent_cfgs = {an: _validate_agent_config(an, get_agent_config(an)) for an in AGENT_CONFIG_KEYS}
    
    def _override_all_agents(model: str, provider: str):
        """Override all agents to the same model + correct provider base_url."""
        prov = PROVIDERS[provider]
        for an in agent_cfgs:
            agent_cfgs[an] = {
                **agent_cfgs[an],
                "model": model,
                "base_url": prov["base_url"],
                "provider": provider,
            }
    
    # ============== SMART ROUTING LOGIC ==============
    # Smart / preset modes override per-agent models + base_url together
    if preset == "smart":
        vision_model = "gemini-3.1-flash-preview"
        synthesis_model = "gemini-3.1-pro-preview"
        _override_all_agents("grok-4-1-fast-reasoning", "xAI Grok")
        st.info("✨ **Smart Mode active**: Gemini Flash (vision) → Grok 4.1 Fast (rounds) → Gemini 3.1 Pro (synthesis)")
    elif preset == "gemini-3.1-vision":
        vision_model = "gemini-3.1-flash-preview"
        synthesis_model = "gemini-3.1-pro-preview"
        _override_all_agents("gemini-3.1-pro-preview", "Google Vertex AI")
    elif preset == "grok-4.2-reasoning":
        vision_model = "grok-4-1-fast-reasoning"
        synthesis_model = "grok-4.20-reasoning"
        _override_all_agents("grok-4.20-reasoning", "xAI Grok")
    elif preset == "grok-4.1-fast":
        vision_model = "grok-4-1-fast-reasoning"
        synthesis_model = "grok-4-1-fast-reasoning"
        _override_all_agents("grok-4-1-fast-reasoning", "xAI Grok")
    else:
        # Per-agent mode — each agent uses its own validated config
        vision_model = agent_cfgs["Planner"]["model"]
        synthesis_model = agent_cfgs["Planner"]["model"]
    
    # ── Safety check: warn if any agent has mismatched config ────
    for an, cfg in agent_cfgs.items():
        if not cfg.get("api_key"):
            st.warning(f"⚠️ **{an}** has no API key configured. It may fail.")
    
    progress_bar = st.progress(0, text="🔍 Agents are analyzing your screenshots with vision...")
    visual_analysis = ""
    if "uploaded_images" in st.session_state and st.session_state.uploaded_images:
        visual_analysis = get_rich_visual_description(
            st.session_state.uploaded_images, 
            st.session_state.get("uploaded_captions", []),
            client
        )
        st.session_state.visual_analysis = visual_analysis
        progress_bar.progress(0.15, text="✅ Vision analysis complete")
    else:
        progress_bar.progress(0.15, text="No screenshots — proceeding with text only")
    
    progress_bar.progress(0.25, text="🤖 Initializing CrewAI agents with per-agent LLMs...")
    try:
        agents = create_vibe_crewai_agents(
            playbooks=playbooks,
            agent_configs=agent_cfgs,
        )
        st.session_state.crewai_agents = agents
        progress_bar.progress(0.35, text="✅ CrewAI agents ready (tools + memory + delegation enabled)")
    except Exception as e:
        st.error(f"Failed to create CrewAI agents: {e}")
        st.stop()
    
    agent_cycle = ["Planner", "BuildPromptWriter", "UIDesigner"]
    prompts_ready = False
    final_round_count = 0
    
    for round_num in range(1, num_rounds + 1):
        final_round_count = round_num
        for agent_name in agent_cycle:
            progress = ((round_num - 1) * 3 + agent_cycle.index(agent_name) + 1) / (num_rounds * 3) * 0.6 + 0.35
            if open_discussion:
                progress_bar.progress(progress, text=f"Round {round_num}/{num_rounds} — {agent_name} is speaking • Open Discussion...")
            else:
                progress_bar.progress(progress, text=f"Round {round_num}/{num_rounds} — {agent_name} is speaking (CrewAI)...")
            
            agent = agents[agent_name]
            response = get_crewai_response(
                agent=agent,
                agent_name=agent_name,
                history=st.session_state.history,
                idea=idea,
                visual_analysis=visual_analysis,
                round_num=round_num
            )
            
            st.session_state.history.append({
                "agent": agent_name,
                "content": response,
                "round": f"Round {round_num}",
                "round_num": round_num,
                "model": agent_cfgs.get(agent_name, {}).get("model", "—"),
                "timestamp": datetime.now().isoformat()
            })
            
            time.sleep(0.35)
        
        # ── Open Discussion quality check ────────────────
        if open_discussion and round_num < num_rounds:
            progress_bar.progress(
                (round_num * 3) / (num_rounds * 3) * 0.6 + 0.35,
                text=f"Round {round_num}/{num_rounds} — 🔍 BuildPromptWriter evaluating prompt quality..."
            )
            
            writer_agent = agents["BuildPromptWriter"]
            eval_task_desc = f"""You have just completed Round {round_num} of collaboration.

Review ALL build prompts produced so far in the discussion transcript.

Are the current build prompts **production-ready**?
A production-ready prompt must have: clear numbered requirements, explicit tool choices, folder structure, success criteria, and the right emotional vibe.

Reply with EXACTLY one of:
- YES - [short reason why they are ready]
- NO - [what still needs improvement]

Nothing else. One line only."""

            eval_task = Task(
                description=eval_task_desc,
                expected_output="YES or NO with a short reason.",
                agent=writer_agent,
            )
            eval_crew = Crew(agents=[writer_agent], tasks=[eval_task],
                             process=Process.sequential, memory=True, verbose=False)
            try:
                eval_result = eval_crew.kickoff()
                eval_text = str(eval_result.raw).strip() if hasattr(eval_result, 'raw') else str(eval_result).strip()
            except Exception:
                eval_text = "NO - evaluation failed, continuing refinement"
            
            # Record the evaluation in history
            st.session_state.history.append({
                "agent": "BuildPromptWriter",
                "content": f"**🔍 Quality Evaluation (Round {round_num}):** {eval_text}",
                "round": f"Round {round_num} — Eval",
                "round_num": round_num,
                "model": agent_cfgs.get("BuildPromptWriter", {}).get("model", "—"),
                "is_eval": True,
                "timestamp": datetime.now().isoformat()
            })
            
            if eval_text.upper().startswith("YES"):
                prompts_ready = True
                progress_bar.progress(0.92,
                    text=f"✅ Prompts declared production-ready after {round_num} rounds!")
                break
            else:
                progress_bar.progress(
                    (round_num * 3) / (num_rounds * 3) * 0.6 + 0.35,
                    text=f"Round {round_num}/{num_rounds} — ❌ Not ready yet. Continuing refinement..."
                )
                time.sleep(0.5)
    
    # ── Synthesis ────────────────────────────────────────
    progress_bar.progress(0.95, text="📦 Final synthesis with CrewAI...")
    
    convergence_note = ""
    if open_discussion:
        if prompts_ready:
            convergence_note = f"\n\n**Note:** Agents converged after {final_round_count} rounds (prompts declared production-ready by BuildPromptWriter)."
        else:
            convergence_note = f"\n\n**Note:** Reached max rounds ({num_rounds}). Prompts may benefit from further refinement."
    
    planner_cfg = agent_cfgs.get("Planner", get_agent_config("Planner"))
    final = synthesize_final_outputs_crewai(
        agents=agents,
        history=st.session_state.history,
        idea=idea,
        visual_analysis=visual_analysis,
        playbooks=playbooks,
        model=synthesis_model,
        api_key=planner_cfg.get("api_key") or os.getenv("OPENAI_API_KEY"),
        base_url=planner_cfg.get("base_url") or os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    )
    st.session_state.final_outputs = final + convergence_note
    
    st.session_state["_debug_launch_status"] = f"✅ Success — {final_round_count} rounds"
    progress_bar.progress(1.0, text="✅ Collaboration complete!")
    if open_discussion and prompts_ready:
        st.success(f"✅ Agents refined prompts to production-ready in {final_round_count} rounds. Scroll down.")
    else:
        st.success("✅ Real CrewAI agents with tools, memory & delegation just finished. Scroll down.")
    st.balloons()

  except Exception as _launch_err:
    _tb = traceback.format_exc()
    st.session_state["_debug_last_error"] = str(_launch_err)
    st.session_state["_debug_last_traceback"] = _tb
    st.session_state["_debug_launch_status"] = f"❌ Failed — {str(_launch_err)[:80]}"
    st.error(f"❌ Launch failed: {_launch_err}")
    st.caption("Open **🔧 Debug & Logs** in sidebar for details.")

if st.session_state.history:
    st.divider()
    st.header("💬 Agent Discussion Transcript (CrewAI Powered)")
    
    for msg in st.session_state.history:
        agent_info = AGENTS[msg['agent']]
        with st.chat_message(msg['agent'].lower(), avatar=agent_info['emoji']):
            _msg_model = msg.get('model', '')
            st.markdown(f"**{msg['agent']}** • *{msg.get('round', '')}* • `{_msg_model}`")
            if msg.get("is_eval"):
                # Quality evaluation — highlight it
                eval_color = "#238636" if "YES" in msg["content"].upper() else "#da3633"
                st.markdown(
                    f'<div style="border-left:3px solid {eval_color};padding:6px 12px;'
                    f'background:#0d1117;border-radius:4px;font-size:0.85rem;">'
                    f'{msg["content"]}</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(msg['content'])
    
    if st.session_state.final_outputs:
        st.divider()
        st.header("📦 Final Deliverables (CrewAI Synthesized)")
        
        tabs = st.tabs(["📋 Project Plan", "🛠️ Build Prompts", "🎨 UI Design System", "❓ Questions & Next Steps"])
        content = st.session_state.final_outputs
        
        with tabs[0]:
            if "## 📋 PROJECT PLAN" in content:
                plan_part = content.split("## 📋 PROJECT PLAN")[1].split("## 🛠️")[0] if "## 🛠️" in content else content.split("## 📋 PROJECT PLAN")[1]
                st.markdown(plan_part.strip())
            else:
                st.markdown(content)
        
        with tabs[1]:
            if "## 🛠️ BUILD PROMPTS" in content:
                prompt_part = content.split("## 🛠️ BUILD PROMPTS")[1].split("## 🎨")[0] if "## 🎨" in content else ""
                st.markdown(prompt_part.strip())
            else:
                st.markdown("See full synthesis below")
        
        with tabs[2]:
            if "## 🎨 UI/UX DESIGN SYSTEM" in content:
                ui_part = content.split("## 🎨 UI/UX DESIGN SYSTEM")[1].split("## ❓")[0] if "## ❓" in content else ""
                st.markdown(ui_part.strip())
            else:
                st.markdown("See full synthesis below")
        
        with tabs[3]:
            if "## ❓ CLARIFYING QUESTIONS" in content:
                q_part = content.split("## ❓ CLARIFYING QUESTIONS")[1].split("## 🚀")[0] if "## 🚀" in content else ""
                st.markdown(q_part.strip())
            if "## 🚀 NEXT STEPS" in content:
                next_part = content.split("## 🚀 NEXT STEPS")[1]
                st.markdown(next_part.strip())
        
        with st.expander("📜 Full Raw Synthesis (copy everything)"):
            st.code(st.session_state.final_outputs, language="markdown")
        
        st.divider()
        st.header("🧠 Continue with VibeCoder Assistant")
        st.caption("Ask anything — refine prompts, generate code snippets, change tech choices, or get implementation help. Full team context + vision analysis loaded.")
        
        if "vibe_chat" not in st.session_state:
            st.session_state.vibe_chat = []
        
        for chat_msg in st.session_state.vibe_chat:
            with st.chat_message(chat_msg["role"]):
                st.markdown(chat_msg["content"])
        
        if user_q := st.chat_input("Ask VibeCoder (e.g. 'Make the build prompt for the dashboard stricter on TypeScript and add Framer Motion')"):
            st.session_state.vibe_chat.append({"role": "user", "content": user_q})
            
            client = get_client()
            context = f"""You are VibeCoder — the combined brain of Planner + BuildPromptWriter + UIDesigner (powered by CrewAI).
Active preset: {st.session_state.get('model_preset', 'smart')}
You have access to the full discussion, final deliverables, and visual analysis of user screenshots.

PROJECT IDEA: {idea}
VISUAL ANALYSIS: {st.session_state.get('visual_analysis', '')[:1200]}
DISCUSSION SUMMARY: {st.session_state.final_outputs[:1800]}

User question: {user_q}

Answer helpfully, structured, and in the same high-quality harsh-but-constructive vibe as the team. If they want code or updated prompts, provide it."""

            with st.chat_message("assistant"):
                chat_cfg = get_active_config()
                response = client.chat.completions.create(
                    model=chat_cfg["model"],
                    messages=[{"role": "system", "content": context}, {"role": "user", "content": user_q}],
                    temperature=0.6,
                    max_tokens=1500
                ).choices[0].message.content
                st.markdown(response)
                st.session_state.vibe_chat.append({"role": "assistant", "content": response})

st.divider()
with st.expander("ℹ️ How v2 Works (CrewAI + Vision)"):
    st.markdown("""
    **What's New in v2:**
    - **Real CrewAI Agents**: Your Planner, BuildPromptWriter, and UIDesigner are now first-class CrewAI agents with:
      - Dedicated **tools** (they can read all playbooks on demand)
      - **Memory** (they remember previous turns within the crew)
      - **Delegation** capability (they can hand off to teammates intelligently)
    - **Vision Support**: When you upload screenshots, gpt-4o analyzes them in rich detail. The analysis is injected into every agent's context so they can literally "see" your references.
    - **Same beloved UX**: The beautiful transcript, harsh teacher personality, structured outputs, and Vibe Coder follow-up chat are all preserved.

    **Under the hood**: Each round creates a mini-Crew with the speaking agent + tools + memory. The final synthesis is also a CrewAI task.

    **Future extensions** (easy to add):
    - Code execution tool for the Prompt Writer
    - Web search / browser tool for research
    - Actual Figma / image generation tool calls
    - Persistent long-term memory across sessions

    Built with ❤️ for vibe coders who want coworkers that actually ship.
    """)

st.caption("VibeAgents v2.5.0 • Debug Tools • Per-Agent LLM • May 2026")
