"""Autonomous Subagent Bridge & Dispatch CLI for Portfolio Lab & AI-File-Exchange.

Eliminates manual prompt copy-pasting across models (Claude Opus 5.5, Gemini 4 Argon, ChatGPT 6).

Usage:
    python scripts/agent_bridge.py list
    python scripts/agent_bridge.py dispatch <stream_or_task_name>
    python scripts/agent_bridge.py ingest <output_file_name>
    python scripts/agent_bridge.py watch
"""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import subprocess
import sys
import time

DRIVE_ROOT = Path(r"G:\My Drive\AI-File-Exchange")
SUBAGENTS_DIR = DRIVE_ROOT / "05 Subagents"
TASKS_DIR = SUBAGENTS_DIR / "Tasks"
OUTPUTS_DIR = SUBAGENTS_DIR / "Outputs"
SPECS_DIR = DRIVE_ROOT / "03 Investment Portfolio" / "V8.0 - Portfolio Construction Lab" / "00 Specifications"
RESOURCES_DIR = DRIVE_ROOT / "03 Investment Portfolio" / "V8.0 - Portfolio Construction Lab" / "01 Resources"
LOCAL_REPO = Path(__file__).resolve().parent.parent
FIXTURES_DIR = LOCAL_REPO / "tests" / "fixtures"

FORBIDDEN_ESCAPES = (
    (r"\\_", "_"),
    (r"\\\[", "["),
    (r"\\\]", "]"),
    (r"\\&", "&"),
    (r"\\\+", "+"),
    (r"\\<=", "<="),
)


def copy_to_clipboard(text: str) -> bool:
    """Copy text to Windows clipboard via clip.exe."""
    try:
        proc = subprocess.Popen(["clip.exe"], stdin=subprocess.PIPE, shell=True)
        proc.communicate(input=text.encode("utf-16"))
        return True
    except Exception as exc:
        print(f"[!] Clipboard error: {exc}", file=sys.stderr)
        return False


def cmd_list() -> None:
    """List all tasks and their completion status."""
    print("=" * 70)
    print("SUBAGENT TASK PIPELINE STATUS")
    print("=" * 70)
    if not TASKS_DIR.exists():
        print(f"[!] Tasks directory not found at {TASKS_DIR}")
        return

    tasks = sorted(TASKS_DIR.glob("*.md"))
    outputs = {p.stem.lower(): p for p in OUTPUTS_DIR.glob("*.md")} if OUTPUTS_DIR.exists() else {}

    for t in tasks:
        stem = t.stem
        # Check if corresponding result exists (e.g. Stream_A -> Stream_A_Result)
        result_key = f"{stem.lower()}_result"
        direct_key = stem.lower()
        has_output = result_key in outputs or direct_key in outputs
        status = "[DONE]" if has_output else "[PENDING]"
        print(f" {status:<10} {t.name:<25} -> {t}")

    print("=" * 70)


def cmd_dispatch(task_name: str) -> None:
    """Generate 1-line trigger for cloud agents with Google Drive connector and copy to clipboard."""
    if not task_name.endswith(".md"):
        task_name += ".md"

    task_path = TASKS_DIR / task_name
    if not task_path.exists():
        candidates = list(TASKS_DIR.glob(f"*{task_name}*"))
        if candidates:
            task_path = candidates[0]
            task_name = task_path.name
        else:
            print(f"[!] Task file not found: {task_path}")
            return

    # Derive canonical target output path
    out_name = f"{task_path.stem}_Result.md"
    one_liner = (
        f'@Google Drive Please read and execute "05 Subagents/Tasks/{task_name}" '
        f'and write your substantive deliverable directly to "05 Subagents/Outputs/{out_name}". '
        f'Do not dump voluminous text into chat.'
    )

    print("\n" + "=" * 70)
    print(f"DISPATCH TRIGGER FOR: {task_name}")
    print("=" * 70)
    print(one_liner)
    print("=" * 70)

    if copy_to_clipboard(one_liner):
        print("[OK] Copied 1-line trigger directly to Windows Clipboard!")
        print("     Paste (Ctrl+V) into ChatGPT Web or Gemini App to launch subagent.")
    else:
        print("[!] Could not auto-copy to clipboard. Please copy the line above manually.")


def clean_markdown_escapes(content: str) -> str:
    """Strip Google Docs escaping artifacts."""
    for pattern, replacement in FORBIDDEN_ESCAPES:
        content = re.sub(pattern, replacement, content)
    # Remove file boundary markers if accidentally present inside text
    content = re.sub(r"^=== (BEGIN|END) FILE.*?===\n?", "", content, flags=re.MULTILINE)
    return content


def cmd_ingest(filename: str) -> None:
    """Clean markdown artifacts, sync with fixtures, and run contract tests."""
    target_path = OUTPUTS_DIR / filename
    if not target_path.exists():
        print(f"[!] Output file not found: {target_path}")
        return

    raw = target_path.read_text(encoding="utf-8")
    cleaned = clean_markdown_escapes(raw)
    if cleaned != raw:
        target_path.write_text(cleaned, encoding="utf-8")
        print(f"[OK] Cleaned Google Docs escape artifacts in {target_path.name}")

    print("[*] Running local contract verification gate (pytest)...")
    res = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_v8_contracts.py"],
        cwd=str(LOCAL_REPO),
        capture_output=True,
        text=True,
    )
    if res.returncode == 0:
        print("[PASS] All contract checks passed!")
    else:
        print("[FAIL] Contract verification failed:\n", res.stdout, res.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(description="Subagent Bridge & Dispatch CLI")
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    subparsers.add_parser("list", help="List all subagent tasks and completion status")

    p_dispatch = subparsers.add_parser("dispatch", help="Generate 1-line cloud trigger and copy to clipboard")
    p_dispatch.add_argument("task", help="Task filename or stream name (e.g. Stream_A, Task_04)")

    p_ingest = subparsers.add_parser("ingest", help="Clean markdown artifacts and verify contracts")
    p_ingest.add_argument("file", help="Filename in 05 Subagents/Outputs/")

    args = parser.parse_args()
    if args.subcommand == "list":
        cmd_list()
    elif args.subcommand == "dispatch":
        cmd_dispatch(args.task)
    elif args.subcommand == "ingest":
        cmd_ingest(args.file)


if __name__ == "__main__":
    main()
