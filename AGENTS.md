# Universal Multi-Model Governance & Workflow Protocol

**Single Source of Truth** for Claude Opus 5.5 (Antigravity), ChatGPT 6 (Cloud & Chat Mode), Gemini 4 Argon, Gemini 3.8 Flash, and Local Codex CLI.  
**Last Updated:** 18 October 2026.

---

## 1. Top-Level Workspace Architecture

The system operates across three strictly segregated roots. Never cross-contaminate files between them:

| Tier | Root Path | Role & Contents | Permitted Operations |
| :--- | :--- | :--- | :--- |
| **1. Code Execution (Local)** | `C:\Users\home\Documents\AI-Disk-Access` | Local project repositories, Python virtual environments, Git repositories, worktrees, and test harnesses. | Code editing, running tests, Git staging/commits. **Never store non-code assets or documents here.** |
| **2. Active Hub (Cloud)** | `G:\My Drive\AI-File-Exchange` (synced via Google Drive Desktop) | **Active working files only.** Mathematical specifications, verified universe CSVs, candidate master CVs, handovers, and current status dashboard. | Reading specifications, updating active files, writing deliverables. **Never store `.git`, `.venv`, or internal `Archive/` folders here.** |
| **3. External Archive (Cold Storage)** | `G:\My Drive\AI Archive & Backups` (external top-level folder) | Major milestone backups, superseded repo baselines, and permanent project snapshots. | Read-only cold storage. **Kept outside `AI-File-Exchange` to eliminate semantic search collisions for cloud agents.** |

---

## 2. Archive & File Hygiene Rules

1. **Top-Level Archive Destination:** All archives live exclusively in `G:\My Drive\AI Archive & Backups\`. **Never create internal `Archive/` subfolders inside `AI-File-Exchange`.**
2. **Major Milestones Only:** Only major architectural transitions (e.g. complete version releases like `V7_final_snapshot` or repository backups) are archived. Never archive micro-drafts, broken test files, or every intermediate edit.
3. **Delete Ephemeral Data:** Scratch notes, temporary test scripts, and superseded prompts must be deleted immediately, not archived.
4. **Zero Semantic Search Poisoning:** Cloud agents (`@Google Drive` in Gemini and Drive Search in ChatGPT) execute flat vector queries. Keeping `AI-File-Exchange` lean and free of duplicate filenames prevents stale context injection.

---

## 3. Communication Standards & ASD-STE100 Protocol

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
   * **Subagent Work Delegation:** Every delegated task must be treated as independent subagent work with strict input contracts, file destinations, and exit criteria. If 4 subagents are insufficient, create additional specialized subagents.
4. **Cloud Prompt Dispatch & Chat Naming Standard:**
   * **Mandatory Execution Parameters:** When presenting prompts for external cloud execution, specify:
     - **ChatGPT:** App (`ChatGPT Web` vs `ChatGPT Desktop App`), Project (`Rob - Cloud` [Chat Mode] vs `Rob - Local` [Work Mode / Codex CLI strictly; NO Chat Mode]), and Mode (`Chat Mode` vs `Work Mode`).
     - **Gemini App:** Gem (`Gem ON` vs `Gem OFF`), Reasoning (`High` vs `OFF`), and explicit `@Google Drive` trigger line.
     - **Antigravity:** Native local IDE execution; no cloud toggles apply.
   * **Descriptive Title Tag for Tab Naming:** The first line inside every copy-and-paste prompt block MUST begin with a 2–6 word bracketed title (e.g. `[ETF Research - Residual Quote Units Audit]`) so the browser tab is immediately named and distinguishable.

---

## 4. Multi-Model Platform Stack & Routing

| Model Tier | Platform / Model | Quota Structure | Core Responsibilities |
| :--- | :--- | :--- | :--- |
| **Orchestrator / Coder** | **Claude Opus 5.5** (Antigravity) / **Codex CLI** | 5-Hour & 1-Week Rolling Caps | Central integration gate, Python 3.14 code, red-to-green `pytest`, LaTeX compilation. |
| **Deep Reasoner / Auditor** | **Gemini 4 Argon** (App / Antigravity) / **GPT-6 Astra / Sol** | 5-Hour & 1-Week Rolling Caps | Deep primary research (export to Google Drive or download file), tabular ETF audits, complex MIQP derivations. |
| **High-Volume Workhorse** | **ChatGPT 6 (Chat Mode)** | **UNLIMITED** | High-volume reading, 4-Stage candidate mapping, company research, iterative document drafting. |
| **Fast QA Runner** | **Gemini 3.8 Flash** (Antigravity) | High Throughput | Fast `pytest` execution, syntax validation, linting, and rapid text formatting. |
| **Offline Privacy / Scrubbing** | **Qwen 2.5 32B Abliterated** (Ollama / Chatbox) | **UNMETERED / LOCAL** | PII and credential redaction, safety-filter bypass for sensitive data, offline contingency. |

---

## 5. Candidate Evidence & CV Architecture

1. **Canonical Evidence Matrix:** `01 Career & Portfolio/Master_Evidence_Matrix.yaml` is the immutable source of truth for all candidate metrics.
2. **Employer Factual Lock:** Strictly **Breathe Partners** (Commercial & Operations Analyst | EV charging infrastructure consultancy). Prohibit "Breathe Battery Technologies" or "Battery Tech".
3. **Four-Stage Tailoring Overlay:** Follow the restored 4-stage contract in `02 Job Search/Instructions & Context/`:
   * *Stage 1:* Role Discovery & Candidate Mapping
   * *Stage 2:* Evidence Audit & Fact Verification
   * *Stage 3:* Editorial Optimization (`cv_editorial_ranker.py`)
   * *Stage 4:* LaTeX Generation & Space Utilization
4. **Master Reference Baseline:** `02 Job Search/Quality Engine/CV_Master_Best_Of_All.tex` (supported by `CV_Template.tex`). Must compile to **strictly 1 A4 page**:
   * **Geometry & Font:** `left=1.3cm, right=1.3cm, top=1.1cm, bottom=1.1cm`, `a4paper, 11pt`, `lmodern` (Latin Modern Roman), `microtype`.
   * **Header & Spacing:** Centered `{\Huge Robert Gardner}\\[5pt]` followed by single-line `\small` contact bar with FontAwesome icons (`\faLinkedin\ LinkedIn`, `\faGithub\ GitHub Portfolio`, `\faEnvelope\ mail@robertgardner.co.uk`, `\faMobile*\ +44 7398 158817`, `London, UK`) separated by `\hspace{0.7em}\textbar\hspace{0.7em}`, and `\vspace{-4.62pt}` after `\end{center}`.
   * **Sections & Lists:** `\titlespacing*{\section}{0pt}{6pt}{4.2pt}`, `\cventry` with `tabularx{\linewidth}{@{}X r@{}}` and `\vspace{-13pt}`, `cvitems` with `leftmargin=1.25em, itemsep=1.5pt, topsep=0pt, parsep=0pt, partopsep=0pt` and trailing `\vspace{4pt}`, inter-entry `\vspace{3.5pt}`.
   * **Content Structure:** Strictly `3 + 2` rendered lines in Profile (`\vspace{1pt}` before P1, `\vspace{4pt}` between P1 and P2); immutable Education block (`{\mdseries 2:1, 69\% overall, 72\% final year}`); **19 single-line bullets** (`4` Breathe + `2` AFL + `1` McDonald's + `4+4+4` across 3 Projects, zero line wrapping).
5. **System Prompts Reference Registry:** `06 System & Maintenance/SYSTEM_PROMPTS_AND_INSTRUCTIONS.md` is strictly a **read-only reference document**. Local agents (`AGENTS.md`, `GEMINI.md`, `antigravity_orchestrator.md`) can be edited directly on disk; cloud UI instructions (ChatGPT Projects, Gemini Gems, Gemini Saved Info) require outputting a copy-and-paste block in chat with explicit UI navigation instructions.
