# Universal Multi-Model Governance & Workflow Protocol

**Single Source of Truth** for Claude Opus 5.5 (1ACO5.5), Gemini 3.8 Flash (Lead Orchestrator / 1AG3.8 / 1Sflash), Gemini 4 Argon (1AG4A / 1Spro / 3AGApp), ChatGPT 6 (2AChatgpt6), ChatGPT Desktop Work Mode (2A Work), Codex CLI (2S Work), Google AI Studio (4AGStudio / 4GS), Groq (6GS), Freebuff (7SFreebuff), Claude Desktop (5CA), and Chatbox / Ollama (8ALocal).  
**Last Updated:** 20 October 2026.

---

## 1. Top-Level Workspace Architecture

The system operates across three strictly segregated roots. Never cross-contaminate files between them:

| Tier | Root Path | Role & Contents | Permitted Operations |
| :--- | :--- | :--- | :--- |
| **1. Code Execution (Local)** | `C:\Users\home\Documents\AI-Disk-Access` | Local project repositories, Python virtual environments, Git repositories, worktrees, and test harnesses. | Code editing, running tests, Git staging/commits. **Never store non-code assets or documents here.** |
| **2. Active Hub (Cloud)** | `G:\My Drive\AI-File-Exchange` (synced via Google Drive Desktop) | **Active working files only.** Mathematical specifications, verified universe CSVs, candidate master CVs, handovers, and current status dashboard. | Reading specifications, updating active files, writing deliverables. **Never store `.git`, `.venv`, or internal `Archive/` folders here.** |
| **3. External Archive (Cold Storage)** | `G:\My Drive\AI Archive & Backups` (external top-level folder) | Major milestone backups, superseded repo baselines, and permanent project snapshots. | Read-only cold storage. **Kept outside `AI-File-Exchange` to eliminate semantic search collisions for cloud agents.** |

---

## 2. Active Hub Directory Structure: Human vs AI Segregation

Inside `G:\My Drive\AI-File-Exchange`, enforce strict segregation between **Human-Facing Assets (01–04)** and **AI Machine Infrastructure (05–10)**:

| Tier | Directory | Primary Content & Formats | Permitted Operations | Prohibited Content |
| :--- | :--- | :--- | :--- | :--- |
| **Human** | **`01 Career & Evidence`** | `.pdf`, `.docx`, `.yaml`, `.csv`. Certified transcripts, credentials, reference letters, `Master_Evidence_Matrix.yaml`. | Candidate evidence verification, record updates. | Ephemeral test files, scraper dumps. |
| **Human** | **`02 Applications & CVs`** | `.pdf`, `.tex`, `.docx`, `.cls`. Compiled 1-page CV PDFs, LaTeX sources, cover letters, application trackers. | CV tailoring, LaTeX compilation, job applications. | Machine logs, Python scripts, raw prompt dumps. |
| **Human** | **`03 Portfolio Deliverables`**| `.pdf`, `.html`, `.csv`, `.docx`. V8 methodology whitepaper, tear sheets, finalized publication datasets (`verified_universe.csv`). | Investor presentations, executive deliverable review. | Code modules, solver cache files, intermediate parquets. |
| **Human** | **`04 Media & Publications`** | `.md` articles, `.pptx`, `.gif`, `.mp4`, `.png`, `.jpg`, `.html`. Published and drafted LinkedIn articles, animated GIFs, 4:5 MP4 videos. | Thought leadership authoring, visual rendering. | Unit tests, subagent task files. |
| **AI** | **`05 Subagent Pipeline`** | `.md`, `.json`, `.csv` (staging). Subagent task manifests (`Tasks/`), returned deliverables (`Outputs/`), `TODO_PIPELINE.md`. | Task queue dispatch, deliverable ingestion, staging. | Permanent human releases, compiled PDFs. |
| **AI** | **`06 System & Governance`** | `.md`, `.toml`, `.yaml`, `.json`. Governance protocols (`AGENTS.md`, `GEMINI.md`), rate registries (`USAGE_AND_RATE_LIMITS.md`), system prompts. | System configuration, token budget governance. | Ephemeral scratch notes, binary media files. |
| **AI** | **`07 Skills Registry`** | `SKILL.md`, `.py`, `.sh`, `.ps1`. Central modular skills linked via Windows directory junctions to local IDEs and agents. | Skill execution, capability extension. | Output deliverables, large datasets. |
| **AI** | **`08 Model Specifications`**| `.md`, `.yaml`, `.json`. Formal mathematical contracts, algorithm designs, product specifications, UI microcopy specs. | Model derivation, algorithm specification audits. | Compiled PDF files, visual media. |
| **AI** | **`09 Machine Data & Parquets`**| `.parquet`, `.npz`, `.joblib`, `.json`, `.csv`. High-performance binary data, CSR matrices, market snapshots. | Algorithmic execution, quantitative backtesting. | Manually edited Word documents. |
| **AI** | **`10 Telemetry & Session Logs`**| `.jsonl`, `.csv`, `.log`, `.md`. Subagent token logs, 5-hour rolling usage logs, unit test logs, solver profiling. | Session audit, token expenditure tracking. | Canonical evidence, permanent specifications. |

---

## 3. Archive & File Hygiene Rules

1. **Top-Level Archive Destination:** All archives live exclusively in `G:\My Drive\AI Archive & Backups\`. **Never create internal `Archive/` subfolders inside `AI-File-Exchange`.**
2. **Major Milestones Only:** Only major architectural transitions (e.g. complete version releases like `V7_final_snapshot` or repository backups) are archived. Never archive micro-drafts, broken test files, or every intermediate edit.
3. **Delete Ephemeral Data:** Scratch notes, temporary test scripts, and superseded prompts must be deleted immediately, not archived.
4. **Zero Semantic Search Poisoning:** Cloud agents (`@Google Drive` in Gemini and Drive Search in ChatGPT) execute flat vector queries. Keeping `AI-File-Exchange` lean and free of duplicate filenames prevents stale context injection.

---

## 4. Communication Standards & ASD-STE100 Protocol

1. **Internal Technical Communication (To User & Between AIs):**
   * Apply ASD-STE100 principles for all technical explanations, reports, agent instructions, READMEs, and skills.
   * Use short, active-voice sentences.
   * State one core idea per sentence.
   * Keep vocabulary precise and eliminate conversational filler.
2. **External / Professional Content:**
   * **Do NOT use ASD-STE100** for employer-facing, interviewer-facing, or commercial client content (e.g., CV bullets, cover letters, client presentations).
   * Maintain natural, high-impact professional prose.
3. **File-First Output & Ultra-Dense Agent Communication Protocol:**
   * **Never dump massive files or drafts into chat:** All models and subagents must write deliverables directly to the target file in `AI-File-Exchange` (or local code repository).
   * **Ultra-Dense Chat Format:** Chat responses must be strictly minimal, dense, and structured:
     `Task: [Task ID / Name] — [Fully Complete | Partially Complete]`
     `Agent: [Assigned Model / Subagent Name]`
     `Output Written To: [Target file path]`
     `Next Do This: [Exact next action, command, or prompt to execute]`
     `Questions for Author: [Crucial clarifying questions / blockers, or "None"]`
   * **Subagent Work Delegation:** Every delegated task must be treated as independent subagent work with strict input contracts, file destinations, and exit criteria.
4. **Cloud Prompt Dispatch & Chat Naming Standard:**
   * **Mandatory Execution Parameters:** When presenting prompts for external execution, specify strictly ONE discrete platform and mode:
     - **For Chat Mode:** App: `ChatGPT Web` (or `ChatGPT Desktop App`), Project: `Rob - Cloud`, Mode: `Chat Mode`, Model: `ChatGPT 6` (or other), Reasoning Effort: `None / Standard`.
     - **For Work Mode (Local Repo):** App: `ChatGPT Desktop App`, Project: `Rob - Local`, Mode: `Work Mode`, Model: `GPT-6 Astra` (or `GPT-6.1 Sol`), Reasoning Effort: `High` (or `Medium`). *(Operated via desktop GUI; no terminal CLI).*
     - **For Gemini App:** App: `Gemini Web / App`, Model: `Gemini 4 Argon`, Reasoning Effort: `High`, and explicit `@Google Drive` trigger line.
     - **For Antigravity:** Platform: `Antigravity IDE (Local)`, Model: `Claude Opus 5.5` or `Gemini 3.8 Flash`.
   * **Descriptive Title Tag for Tab Naming:** The first line inside every copy-and-paste prompt block MUST begin with a 2–6 word bracketed title (e.g. `[ETF Research - Residual Quote Units Audit]`) so the browser tab is immediately named and distinguishable.
5. **Terminology Lock: Agents vs Subagents:**
   * **Interactive Agents (`A`):** Standalone platform sessions (ChatGPT 6 Web, Gemini App, Claude Desktop, Chatbox). Require user navigation, chat dispatch, or GUI interaction.
   * **Autonomous Subagents (`S`):** Autonomous background workers executing programmatically (`invoke_subagent`, CLI scripts). Require zero user copy-paste. Multiple subagents run concurrently.
6. **Minimal Orchestrator Thinking & Fast-Track Pipeline Protocol:**
   * **Minimal Orchestrator Thinking:** The Lead Orchestrator operates as a high-speed traffic controller, dispatcher, and delegator. It never executes deep multi-minute reading or heavy file parsing inside the main chat turn.
   * **Zero-Wait Prompt Dispatch:** When the user reports an external Agent finished Task N, the Orchestrator outputs the Task N+1 prompt immediately without blocking on deep document parsing.
   * **Background Subagent Integration:** Concurrently with prompt dispatch, the Orchestrator spawns an internal native Subagent (`invoke_subagent`) to audit raw deliverables in `05 Subagent Pipeline/Outputs/`, verify schema/contract parity, move integrated files out of staging to permanent paths, and update status registers silently.

---

## 5. Unified Multi-Model System Architecture & Naming Registry

### 5.1 Lead Orchestrator
* **Designation:** `Lead Orchestrator`
* **Model Engine:** **Gemini 3.8 Flash (Always High Reasoning)** inside Google Antigravity.
* **Role:** High-speed traffic controller, dispatcher, quality gate, and delegator.
* **Operational Invariant:** The Orchestrator minimizes main-turn reasoning latency. It never executes solitary multi-minute mathematical derivations or heavy text ingestion in the main thread. It decomposes complex initiatives and delegates execution to specialized subagents.

### 5.2 Interactive Agents Registry (`A`)

Interactive agents require active user navigation, chat tab management, or graphical user interface (GUI) interaction:

| Identifier | Platform / Interface | Exact Model | Reasoning Mode | Quota & Billing Profile | Core Cognitive Specialization |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`1ACO5.5`** | Antigravity IDE | Claude Opus 5.5 | Adaptive / Native | 5-Hour & 1-Week Rolling Windows | Strategic software planning, Python 3.14 architecture, red-to-green `pytest`, Tectonic LaTeX builds. |
| **`1AG3.8`** | Antigravity IDE | Gemini 3.8 Flash | Always High | High Throughput / High Limit | High-speed interactive pair programming, fast contract verification, prompt drafting. |
| **`1AG4A`** | Antigravity IDE | Gemini 4 Argon | Adaptive Thinking | High Rolling Window | Deep mathematical verification, MIQP formulation audit, financial covariance shrinkage proofs. |
| **`2AChatgpt6`** | ChatGPT Web (`Rob - Cloud`) | ChatGPT 6 / GPT-6 Astra | Standard / High | **UNLIMITED** (Chat Mode) | High-volume reading, 4-Stage CV tailoring, bullet crafting, commercial strategy, company intelligence. |
| **`2A Work`** | ChatGPT Desktop (`Rob - Local`) | GPT-6.1 Sol / GPT-6 Astra | Sol: Low–Max<br>Astra: Low–XHigh | 5-Hour & 1-Week Rolling Windows | Desktop Work Mode (GUI only; no terminal CLI). GitHub-connected multi-file repository refactoring. |
| **`3AGApp`** | Gemini Mobile / Web App | Gemini 4 Argon | Argon High Only (Gem retired) | Batch Quota (~10–20 Deep Research/day) | Real-time research, mobile voice dialogue, visual factsheet verification. Uses root Drive landing. |
| **`4AGStudio`** | Google AI Studio Web | Gemini 3.8 Flash / 4 Argon / 3.1 Pro | Configurable | Free Developer Tier / API Key | Web UI prompt engineering, raw parameter tuning, system instruction experimentation. |
| **`5CA`** | Claude Desktop App | Claude Opus 5.5 | Native Reasoning | Standard Desktop Subscription | Standalone desktop assistant; pending MCP server integration. |
| **`8ALocal`** | Chatbox Desktop GUI | `huihui_ai/qwen3.5-abliterated:4B-q4_K` | Native Local (Ollama) | **UNMETERED / 100% OFFLINE** | Confidential document analysis, PII scrubbing, credential redaction, offline contingency. |

### 5.3 Autonomous Subagents Registry (`S`)

Autonomous subagents execute programmatically in the background without manual user copy-paste:

| Identifier | Execution Mechanism | Engine / Model | Reasoning / Parameters | Quota / Cost | Ideal Workload & Constraints |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`1Sflash`** | Native Antigravity (`invoke_subagent`) | Gemini 3.8 Flash | Default / Fast | High Throughput | Parallel swarms (2–4 concurrent), fast unit tests (`pytest`), schema gates (`<0.3s`), linting, file copying. |
| **`1Spro`** | Native Antigravity (`invoke_subagent`) | Gemini 4 Argon / Pro | High / Deep Thinking | Generous Rolling Window | Single-threaded strictly. Heavy math derivations, complex multi-file architectural refactors, landscape audits. Hedge against Codex limits. |
| **`1Sflash-lite`**| Native Antigravity (`invoke_subagent`) | Gemini Flash-Lite | Fast / Low | Maximum Throughput | High-frequency regex search/replace, directory scraping, basic file restructuring. |
| **`2S Work`** | Codex CLI (`codex exec` via PowerShell) | GPT-6.1 Sol / GPT-6 Astra | Sol: Low–Max<br>Astra: Low–XHigh | Quota-Capped (ChatGPT Desktop window) | **Governed by Approval Gate.** Surgical local code implementation, solver bug fixes. Target <= 20% window usage. |
| **`4GS`** | `tools\gemini_subagent.ps1` | `gemini-3.8-flash` / `gemini-4-argon` / `gemini-3.1-pro` | Adjustable via payload | 1,500 RPD / Free API Key (2M Context) | Headless repository auditing, long-context document analysis without consuming IDE quota. |
| **`6GS`** | `tools\groq_subagent.ps1` | `openai/gpt-oss-120b` / `qwen/qwen3.8-27b` | Highest Effort | 14,400 RPD / Free Groq API | Sub-second (<0.4s) headless code analysis, AST syntax verification, fast manifest generation. |
| **`7SFreebuff`**| `tools\freebuff_subagent.ps1` | Gemini 4 Argon + GPT-6 Luna | Highest Effort | 1 Daily Free Session | Standalone daily high-power sweep for complex architecture or difficult multi-file audits. |

---

## 6. Operational Guardrails & Production Invariants

### 6.1 Codex Approval Gate Protocol (`2S Work`)
* **Trigger:** Any planned execution of `codex exec` or programmatic invocation of `2S Work`.
* **Gate Protocol:** Before executing any command with `2S Work`, the Lead Orchestrator MUST:
  1. State the estimated token footprint and message cost of the task.
  2. Estimate current status within the 5-hour rolling usage window (target: preserve headroom so total 5-hour consumption remains <= 20%).
  3. Formulate an explicit, single-line Yes/No question for Robert.
  4. If Robert confirms, proceed with `2S Work`. If Robert rejects or ignores, divert task to `1Spro` (Gemini Pro/Argon in Antigravity) or `4GS` (AI Studio CLI).

### 6.2 Mobile Gemini App Root Dispatch Invariant (`3AGApp`)
* **Problem:** The Gemini mobile client and web app cannot reliably write or navigate to deeply nested subdirectories inside Google Drive.
* **Dispatch Protocol:**
  1. The Orchestrator writes the task dispatch file directly to Google Drive root:  
     `G:\My Drive\Task_<Descriptor>.md`
  2. The prompt provided to the user contains minimal navigation text:  
     `"@Google Drive navigate to Task_<Descriptor>.md and execute the instructions."`
  3. Gemini App generates an output Google Doc deposited at Google Drive root:  
     `G:\My Drive\<Deliverable_Title>.gdoc`
  4. Antigravity Lead Orchestrator scans `G:\My Drive\`, detects the newly generated Google Doc, moves the contents to `05 Subagent Pipeline/Outputs/<Deliverable_Title>.md`, and deletes the root clutter immediately.

### 6.3 Orchestrator Compute Scaling & Heterogeneous Subagents
* **Dynamic Scaling:** The Lead Orchestrator scales compute by dispatching heterogeneous subagents in parallel across distinct streams.
* **Cognitive Matching Matrix:**
  * High-volume reading, applicant profile tailoring -> `2AChatgpt6` (ChatGPT Web - Unlimited).
  * Rapid syntax checking, AST linting, directory inventorying -> `6GS` (Groq LPU CLI - sub-second).
  * Fast test suite verification and schema assertion -> `1Sflash` (Antigravity Flash native).
  * High-context file audits (>100 KB) -> `4GS` (Google AI Studio - 2M context).
  * Formal mathematical and economic derivations -> `1Spro` (Antigravity Pro) or `1AG4A`.
  * Surgical local code refactoring -> `2S Work` (Codex CLI, post-approval).

### 6.4 Ollama & Chatbox Invariant (`8ALocal`)
* **System Lock:** Ollama (`http://127.0.0.1:11434`) hosts `huihui_ai/qwen3.5-abliterated:4B-q4_K` locally for the Chatbox Desktop GUI application.
* **Strict Rule:** Ollama must never be uninstalled, shut down, or configured as a backend for Codex CLI. Codex requires frontier agentic models; Chatbox provides the user interface for unredacted local privacy tasks.

---

## 7. Candidate Evidence & CV Architecture

1. **Canonical Evidence Matrix:** `01 Career & Evidence/Master_Evidence_Matrix.yaml` is the immutable source of truth for all candidate metrics.
2. **Employer Factual Lock:** Strictly **Breathe Partners** (Commercial & Operations Analyst | EV charging infrastructure consultancy). Prohibit "Breathe Battery Technologies" or "Battery Tech".
3. **Four-Stage Tailoring Overlay:** Follow the restored 4-stage contract in `02 Applications & CVs/Instructions & Context/`:
   * *Stage 1:* Role Discovery & Candidate Mapping
   * *Stage 2:* Evidence Audit & Fact Verification
   * *Stage 3:* Editorial Optimization (`cv_editorial_ranker.py`)
   * *Stage 4:* LaTeX Generation & Space Utilization
4. **Master Reference Baseline:** `02 Applications & CVs/Quality Engine/CV_Master_Best_Of_All.tex` (supported by `CV_Template.tex`). Must compile to **strictly 1 A4 page**:
   * **Geometry & Font:** `left=1.3cm, right=1.3cm, top=1.1cm, bottom=1.1cm`, `a4paper, 11pt`, `lmodern` (Latin Modern Roman), `microtype`.
   * **Header & Spacing:** Centered `{\Huge Robert Gardner}\\[5pt]` followed by single-line `\small` contact bar with FontAwesome icons (`\faLinkedin\ LinkedIn`, `\faGithub\ GitHub Portfolio`, `\faEnvelope\ mail@robertgardner.co.uk`, `\faMobile*\ +44 7398 158817`, `London, UK`) separated by `\hspace{0.7em}\textbar\hspace{0.7em}`, and `\vspace{-4.62pt}` after `\end{center}`.
   * **Sections & Lists:** `\titlespacing*{\section}{0pt}{6pt}{4.2pt}`, `\cventry` with `tabularx{\linewidth}{@{}X r@{}}` and `\vspace{-13pt}`, `cvitems` with `leftmargin=1.25em, itemsep=1.5pt, topsep=0pt, parsep=0pt, partopsep=0pt` and trailing `\vspace{4pt}`, inter-entry `\vspace{3.5pt}`.
   * **Content Structure:** Strictly `3 + 2` rendered lines in Profile (`\vspace{1pt}` before P1, `\vspace{4pt}` between P1 and P2); immutable Education block (`{\mdseries 2:1, 69\% overall, 72\% final year}`); **19 single-line bullets** (`4` Breathe + `2` AFL + `1` McDonald's + `4+4+4` across 3 Projects, zero line wrapping).
5. **System Prompts Reference Registry:** `06 System & Governance/SYSTEM_PROMPTS_AND_INSTRUCTIONS.md` is strictly a **read-only reference document**. Local agents (`AGENTS.md`, `GEMINI.md`, `antigravity_orchestrator.md`) can be edited directly on disk; cloud UI instructions (ChatGPT Projects, Gemini Gems, Gemini Saved Info) require outputting a copy-and-paste block in chat with explicit UI navigation instructions.
