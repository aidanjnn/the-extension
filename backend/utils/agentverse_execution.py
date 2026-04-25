"""Execution helpers used by Agentverse agents.

The Agentverse agents decide what to build; this module keeps filesystem,
validation, packaging, and load-instruction behavior inside the FastAPI backend.
"""

from __future__ import annotations

import json
import shutil
import zipfile
from pathlib import Path

from utils.extension_validator import validate_extension
from utils.tools import DEMO_CODE_BASE


TEXT_FILE_SUFFIXES = {
    ".css",
    ".html",
    ".js",
    ".json",
    ".md",
    ".mjs",
    ".txt",
}


def ensure_project_workspace(project_id: str) -> Path:
    project_dir = (DEMO_CODE_BASE / project_id).resolve()
    project_dir.mkdir(parents=True, exist_ok=True)
    return project_dir


def resolve_project_path(project_id: str, relative_path: str) -> Path:
    project_dir = ensure_project_workspace(project_id)
    resolved = (project_dir / relative_path).resolve()
    if not str(resolved).startswith(str(project_dir)):
        raise ValueError(f"Path '{relative_path}' escapes the project workspace")
    return resolved


def write_project_files(project_id: str, files: dict[str, str]) -> list[str]:
    written: list[str] = []
    for relative_path, content in files.items():
        target = resolve_project_path(project_id, relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        written.append(relative_path)
    return written


def read_project_files(project_id: str) -> dict[str, str]:
    project_dir = ensure_project_workspace(project_id)
    files: dict[str, str] = {}
    for path in sorted(project_dir.rglob("*")):
        if not path.is_file() or path.name.startswith("."):
            continue
        if path.suffix.lower() not in TEXT_FILE_SUFFIXES:
            continue
        files[str(path.relative_to(project_dir))] = path.read_text(
            encoding="utf-8",
            errors="replace",
        )
    return files


def validate_project_extension(project_id: str) -> dict:
    project_dir = ensure_project_workspace(project_id)
    issues = validate_extension(project_dir)
    errors = [issue for issue in issues if issue.get("level") == "error"]
    warnings = [issue for issue in issues if issue.get("level") == "warning"]
    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "summary": (
            "Validation passed."
            if not issues
            else f"Validation found {len(errors)} error(s) and {len(warnings)} warning(s)."
        ),
    }


def package_project_extension(project_id: str) -> dict:
    project_dir = ensure_project_workspace(project_id)
    manifest_path = project_dir / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError("No manifest.json found in the project workspace.")

    artifact_dir = DEMO_CODE_BASE / "_artifacts"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    zip_path = artifact_dir / f"{project_id}.zip"

    if zip_path.exists():
        zip_path.unlink()

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(project_dir.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(project_dir))

    return {
        "project_id": project_id,
        "extension_path": str(project_dir),
        "zip_path": str(zip_path),
        "load_instructions": (
            "Open chrome://extensions, enable Developer mode, click Load unpacked, "
            f"and select {project_dir}."
        ),
    }


def get_project_load_info(project_id: str) -> dict:
    project_dir = ensure_project_workspace(project_id)
    return {
        "project_id": project_id,
        "extension_path": str(project_dir),
        "manifest_exists": (project_dir / "manifest.json").exists(),
        "load_instructions": (
            "Open chrome://extensions, enable Developer mode, click Load unpacked, "
            f"and select {project_dir}."
        ),
    }


def reset_project_workspace(project_id: str) -> Path:
    project_dir = (DEMO_CODE_BASE / project_id).resolve()
    if project_dir.exists():
        shutil.rmtree(project_dir)
    project_dir.mkdir(parents=True, exist_ok=True)
    return project_dir


def format_validation_report(report: dict) -> str:
    if report.get("ok"):
        return str(report.get("summary", "Validation passed."))
    return json.dumps(report, indent=2)
