"""Root-cause analysis + healing-strategy selection.

Reads a failed job's log (stdin or path arg), classifies the cause with ordered rules,
and emits a strategy the heal workflow acts on:

  rerun        -> transient/flaky/network: just retry the pipeline
  fix_forward  -> lint/format: run the formatter, commit the fix
  revert       -> real bug or bad dependency: revert the culprit commit via PR
  investigate  -> unknown: open an RCA issue, no automated change

Outputs GitHub Actions outputs (strategy, category, reason) and a human summary.
If ANTHROPIC_API_KEY is set, appends an AI-written narrative diagnosis to the summary —
optional flourish; the deterministic rules decide the action regardless.
"""

import os
import re
import sys

# Ordered: first match wins. Most specific / most safely-automatable first.
RULES = [
    (
        "flaky",
        r"simulated flaky failure|rerun|flake|timeout|ETIMEDOUT|connection reset|temporarily unavailable",
        "rerun",
        "Transient or flaky failure — safe to retry.",
    ),
    (
        "lint",
        r"ruff|would reformat|lint|E\d{3}|F\d{3}|code style",
        "fix_forward",
        "Formatting/lint violation — auto-fixable by running the formatter.",
    ),
    (
        "dependency",
        r"No matching distribution|ResolutionImpossible|Could not find a version|npm ERR|version solving failed",
        "revert",
        "Dependency resolution failure — likely a bad pin; revert the change.",
    ),
    (
        "test_failure",
        r"assert|AssertionError|FAILED tests/|[1-9]\d* failed",
        "revert",
        "Genuine test failure — revert the culprit commit for review.",
    ),
    (
        "build",
        r"SyntaxError|ImportError|ModuleNotFoundError|cannot import name",
        "revert",
        "Build/import error — revert the culprit commit.",
    ),
]


def classify(log: str):
    for category, pattern, strategy, reason in RULES:
        if re.search(pattern, log, re.IGNORECASE):
            return category, strategy, reason
    return "unknown", "investigate", "Cause not recognized — needs human review."


def ai_narrative(log: str) -> str:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return ""
    try:
        import urllib.request
        import json

        body = json.dumps(
            {
                "model": "claude-sonnet-4-6",
                "max_tokens": 300,
                "messages": [
                    {
                        "role": "user",
                        "content": "You are a CI/CD SRE. In 3-4 sentences, diagnose the "
                        "root cause of this failed build log and suggest the fix:\n\n"
                        + log[-4000:],
                    }
                ],
            }
        ).encode()
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=body,
            headers={
                "x-api-key": key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
        )
        r = urllib.request.urlopen(req, timeout=30)
        data = json.load(r)
        return "".join(b.get("text", "") for b in data.get("content", []))
    except Exception as e:
        return f"(AI narrative unavailable: {e})"


def main() -> int:
    log = (
        pathlib.Path(sys.argv[1]).read_text(errors="replace")
        if len(sys.argv) > 1
        else sys.stdin.read()
    )
    category, strategy, reason = classify(log)

    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a") as f:
            f.write(f"strategy={strategy}\n")
            f.write(f"category={category}\n")
            f.write(f"reason={reason}\n")

    summary = f"## 🔍 RCA Result\n\n- **Category:** {category}\n- **Strategy:** `{strategy}`\n- **Reason:** {reason}\n"
    narrative = ai_narrative(log)
    if narrative:
        summary += f"\n### AI diagnosis\n{narrative}\n"

    print(summary)
    step_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if step_summary:
        with open(step_summary, "a") as f:
            f.write(summary)
    return 0


if __name__ == "__main__":
    import pathlib

    sys.exit(main())
