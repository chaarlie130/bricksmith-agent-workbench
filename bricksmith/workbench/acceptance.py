"""Final build acceptance: collect evidence without conflating tools with success."""
from __future__ import annotations

from pathlib import Path
import subprocess
import sys
from typing import Any

from bricksmith.workbench.feedback import check_model

CHECK_NAMES = (
    "mesh_collision_free",
    "included_base",
    "no_parts_below_ground",
    "actual_connectivity",
    "approximate_gravity_equilibrium",
)


def piece_count(path: Path) -> int:
    return sum(1 for line in path.read_text(encoding="utf-8", errors="replace").splitlines()
               if line.strip().startswith("1 "))


def _placement_signature(path: Path) -> tuple[str, ...]:
    return tuple(line.strip() for line in path.read_text(encoding="utf-8", errors="replace").splitlines()
                 if line.strip().startswith("1 "))


def _check(path: Path, ground_y: float) -> dict[str, Any]:
    try:
        raw = check_model(path, ground_y=ground_y)
    except Exception as exc:  # tool/runtime failures are evidence gaps, not passes
        return {"status": "unavailable", "detail": f"{type(exc).__name__}: {exc}", "raw": None}
    checks = raw.get("checks") or {}
    states = {name: checks.get(name) if isinstance(checks.get(name), bool) else None
              for name in CHECK_NAMES}
    complete = all(value is not None for value in states.values())
    passed = complete and all(states.values()) and raw.get("passed") is True
    errors = raw.get("errors", [])
    tool_unavailable = any(error.get("kind") == "environment_error" for error in errors)
    return {
        "status": "passed" if passed else ("unavailable" if tool_unavailable or not complete and not errors
                                            else "failed"),
        "checks": states,
        "errors": errors,
        "detail": None if complete else "One or more construction checks were not produced.",
        "raw": raw,
    }


def _render(ldr: Path, out: Path, azimuth: float) -> dict[str, Any]:
    out.parent.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, "scripts/render.py", str(ldr), "--output", str(out),
               "--azimuth", str(azimuth), "--elevation", "28"]
    try:
        run = subprocess.run(command, capture_output=True, text=True, check=False)
        ok = run.returncode == 0 and out.is_file() and out.stat().st_size > 0
        return {"path": str(out), "command_succeeded": run.returncode == 0,
                "created": out.is_file(), "status": "rendered" if ok else "failed",
                "returncode": run.returncode, "stderr": run.stderr.strip() or None}
    except Exception as exc:
        return {"path": str(out), "command_succeeded": False, "created": False,
                "status": "unavailable", "detail": f"{type(exc).__name__}: {exc}"}


def make_acceptance_report(
    ldr_path: Path,
    *,
    ground_y: float = 8.0,
    min_pieces: int = 500,
    max_pieces: int = 1000,
    stage_models: list[Path] | None = None,
    stage_checks: list[dict[str, Any]] | None = None,
    inspected_views: list[str] | None = None,
    render_dir: Path | None = None,
) -> dict[str, Any]:
    if min_pieces < 1 or max_pieces < min_pieces:
        raise ValueError("Piece target must have 1 <= min_pieces <= max_pieces")
    ldr_path = ldr_path.resolve()
    report: dict[str, Any] = {
        "schema": "bricksmith-build-acceptance-v1",
        "model": str(ldr_path),
        "piece_count": piece_count(ldr_path) if ldr_path.is_file() else None,
        "piece_target": {"minimum": min_pieces, "maximum": max_pieces},
        "ground_y_ldu": ground_y,
        "stage_checks": [],
        "stage_validation_recorded": False,
        "renders": [],
        "inspected_views": sorted(set(inspected_views or [])),
        "construction": {"status": "unavailable", "checks": {n: None for n in CHECK_NAMES}},
        "accepted": False,
    }
    if not ldr_path.is_file():
        report["construction"] = {"status": "unavailable", "checks": {n: None for n in CHECK_NAMES},
                                  "errors": [{"kind": "missing_model", "path": str(ldr_path)}]}
        return report
    stage_models = stage_models or []
    stage_placements: list[tuple[str, ...]] = []
    for stage_model in stage_models:
        stage_path = stage_model.resolve()
        if stage_path.is_file():
            stage_placements.append(_placement_signature(stage_path))
        stage_report = _check(stage_path, ground_y) if stage_path.is_file() else {
            "status": "unavailable", "errors": [{"kind": "missing_stage_model", "path": str(stage_path)}]
        }
        report["stage_checks"].append({"model": str(stage_path), **{
            key: value for key, value in stage_report.items() if key != "raw"
        }})
    # Kept for programmatic reporting/tests; CLI users supply real stage files above.
    if stage_checks:
        report["stage_checks"].extend(stage_checks)
    report["stage_validation_recorded"] = bool(report["stage_checks"])
    final = _check(ldr_path, ground_y)
    checked_count = (final.get("raw") or {}).get("physical_piece_count")
    if isinstance(checked_count, int):
        report["piece_count"] = checked_count
    report["construction"] = {k: v for k, v in final.items() if k != "raw"}
    if render_dir is not None:
        render_dir = render_dir.resolve()
        report["renders"] = [
            _render(ldr_path, render_dir / "front-left.png", 215.0),
            _render(ldr_path, render_dir / "front-right.png", 325.0),
        ]
    renders_ok = len(report["renders"]) == 2 and all(r["status"] == "rendered" for r in report["renders"])
    inspected = {"front_left", "front_right"}.issubset(report["inspected_views"])
    stages_ok = report["stage_validation_recorded"] and all(
        isinstance(stage, dict) and stage.get("status") == "passed" for stage in report["stage_checks"]
    )
    stages_progressed = (len(stage_models) >= 3 and len(stage_placements) == len(stage_models)
                         and len(set(stage_placements)) == len(stage_placements))
    target_met = min_pieces <= report["piece_count"] <= max_pieces
    report["workflow"] = {"major_stages_validated": stages_ok,
                           "major_stages_progressed": stages_progressed,
                           "piece_target_met": target_met,
                           "two_final_views_rendered": renders_ok,
                           "two_final_views_inspected": inspected}
    report["accepted"] = (final["status"] == "passed" and stages_ok and stages_progressed
                          and target_met and renders_ok and inspected)
    return report
