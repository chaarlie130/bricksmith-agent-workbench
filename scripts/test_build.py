#!/usr/bin/env python3
"""Run one bounded ChatGPT-plan LEGO build pilot with local references/checks."""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bricksmith.workbench.chatgpt_plan import ask
from bricksmith.workbench.feedback import check_model
from bricksmith.workbench.prompt import load_system_prompt
from bricksmith.workbench.references import DEFAULT_CORPUS, inspect_model, load_references, search


def extract_ldr(response: str) -> str:
    """Keep only LDraw type-0/type-1 lines and reject malformed/empty builds."""
    lines = []
    parts = 0
    for raw in response.splitlines():
        line = raw.strip()
        if line.startswith("0 "):
            lines.append(line)
        elif line.startswith("1 "):
            tokens = line.split()
            if len(tokens) != 15 or not re.fullmatch(r"[\w.-]+\.dat", tokens[-1], re.I):
                raise ValueError(f"Malformed LDraw part line: {line[:120]}")
            try:
                int(tokens[1])
                for value in tokens[2:14]:
                    float(value)
            except ValueError as exc:
                raise ValueError(f"Non-numeric LDraw placement: {line[:120]}") from exc
            lines.append(line)
            parts += 1
    if not 20 <= parts <= 200:
        raise ValueError(f"Expected 20–200 part placements; got {parts}")
    return "\n".join(lines) + "\n"


def make_prompt(brief: str, repair_from: Path | None = None) -> tuple[str, list[dict]]:
    matches = search(load_references(DEFAULT_CORPUS), "small house roof porch", limit=8)
    choices = [entry for entry in matches if entry["id"] in {
        "omr_1854-1_House_with_Roof-Windows_Velux", "omr_21009-1_Farnsworth_House"}]
    if len(choices) != 2:
        raise RuntimeError("Expected house construction references were not found")
    snippets = []
    for entry in choices:
        excerpt = inspect_model(Path(entry["path"]), start=3, count=35)
        snippet = "\n".join(item["text"] for item in excerpt["excerpt"])
        snippets.append(f"Reference {entry['id']} (sha256 {entry['sha256']}; technique only):\n{snippet}")
    prompt = (
        f"Build brief: {brief}\n\n"
        "Create ONE original 40–90-piece LDraw .ldr model. Output ONLY LDraw lines, "
        "starting with a type-0 title, then one type-1 line per real part. "
        "Keep all coordinates on a coherent 20-LDU stud grid and levels on 8/24-LDU "
        "plate/brick increments. Use common parts such as 3001, 3002, 3003, 3004, "
        "3005, 3010, 3020, 3023, 3024, 3039, 3040b, 3031, 3034. "
        "Prioritize a continuous base, connected wall courses, clear door/window shapes, "
        "and a securely supported pitched roof. No unsupported roof tiles or invented parts. "
        "Do not copy a reference model; use these excerpts only to learn placement conventions.\n\n"
        + "\n\n".join(snippets)
    )
    if repair_from is not None:
        old_model = (repair_from / "build.ldr").read_text(encoding="utf-8")
        old_report = json.loads((repair_from / "report.json").read_text(encoding="utf-8"))
        errors = old_report.get("validation", {}).get("errors", [])
        prompt += (
            "\n\nREPAIR ATTEMPT: The previous model below failed BrickSmith validation. "
            "Keep the cottage brief, but revise the complete .ldr to remove exact "
            "collisions and connect all roof pieces by valid stud/tube attachments. "
            "The roof was the main problem; rebuild its support and tile geometry "
            "instead of merely moving the overlapping slopes. A simpler roof is "
            "preferable to unsupported decorative detail. Output the FULL revised "
            "model, not a patch.\n\nPrevious model:\n" + old_model +
            "\nValidation errors:\n" + json.dumps(errors, separators=(",", ":"))
        )
    return prompt, choices


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--brief", required=True)
    parser.add_argument("--model", default="gpt-5.6-sol")
    parser.add_argument("--output-dir", type=Path,
                        default=ROOT / "runs" / f"pilot-{datetime.now(timezone.utc):%Y%m%d-%H%M%S}")
    parser.add_argument("--repair-from", type=Path, help="include a previous pilot model and its checker feedback")
    parser.add_argument("--dry-run", action="store_true", help="show request size without using plan allowance")
    args = parser.parse_args()
    prompt, references = make_prompt(args.brief, args.repair_from)
    if args.dry_run:
        print(json.dumps({"model": args.model, "brief": args.brief,
                          "prompt_chars": len(prompt),
                          "references": [ref["id"] for ref in references]}, indent=2))
        return 0
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=False)
    (output / "brief.txt").write_text(args.brief + "\n", encoding="utf-8")
    (output / "request.txt").write_text(prompt, encoding="utf-8")
    print(f"Requesting one {args.model} build; saving artifacts in {output}", flush=True)
    raw = ask(args.model, prompt, load_system_prompt())
    (output / "response.txt").write_text(raw, encoding="utf-8")
    report = {"model": args.model, "brief": args.brief,
              "repair_from": str(args.repair_from.resolve()) if args.repair_from else None,
              "references": [{key: ref[key] for key in ("id", "path", "sha256", "license")}
                             for ref in references]}
    try:
        ldr = extract_ldr(raw)
        model_path = output / "build.ldr"
        model_path.write_text(ldr, encoding="utf-8")
        report["part_count"] = sum(line.startswith("1 ") for line in ldr.splitlines())
        report["validation"] = check_model(model_path)
        try:
            from bricksmith.rendering.rasterizer import render_ldr_to_png
            render_ldr_to_png(model_path, output / "preview.png", resolution=800)
            report["preview"] = str(output / "preview.png")
        except Exception as exc:
            report["render_error"] = str(exc)
    except (ValueError, RuntimeError) as exc:
        report["build_error"] = str(exc)
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output_dir": str(output), "part_count": report.get("part_count"),
                      "passed": report.get("validation", {}).get("passed"),
                      "build_error": report.get("build_error"),
                      "render_error": report.get("render_error")}, indent=2))
    return 0 if "build_error" not in report else 2


if __name__ == "__main__":
    raise SystemExit(main())
