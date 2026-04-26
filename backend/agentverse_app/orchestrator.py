"""Agentverse Orchestrator role and local bridge helpers."""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncGenerator
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv

from agentverse_app import backend_client
from agentverse_app.architect import run_architect
from agentverse_app.codegen import run_codegen
from agentverse_app.config import settings
from agentverse_app.messages import (
    AgentStepResult,
    ArchitectRequest,
    CodegenRequest,
    ExtensionBuildRequest,
    ExtensionBuildResult,
    ExtensionSpec,
    PackageRequest,
    RagRequest,
    ValidationRequest,
)
from agentverse_app.packager import run_packager
from agentverse_app.rag import run_rag
from agentverse_app.validator import run_validator


def create_build_request(
    query: str,
    project_id: str,
    provider: str = "gemini",
    source: str = "local",
    active_tabs: list[dict] | None = None,
) -> ExtensionBuildRequest:
    return ExtensionBuildRequest(
        job_id=uuid4().hex,
        project_id=project_id,
        query=query,
        provider=provider,
        source=source,
        active_tabs=active_tabs or [],
    )


def _step(agent_name: str, summary: str, payload: dict | None = None) -> AgentStepResult:
    return AgentStepResult(
        agent_name=agent_name,
        status="ok",
        summary=summary,
        payload=payload or {},
    )


def _short(value: str, limit: int = 72) -> str:
    value = " ".join(str(value).split())
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip() + "…"


def _artifact_event(
    stage: str,
    agent: str,
    title: str,
    summary: str,
    meta: list[dict[str, str]] | None = None,
    chips: list[str] | None = None,
) -> dict:
    return {
        "type": "agent_artifact",
        "artifact": {
            "stage": stage,
            "agent": agent,
            "title": title,
            "summary": _short(summary, 160),
            "meta": meta or [],
            "chips": [_short(chip, 40) for chip in (chips or []) if chip],
        },
    }


def _download_url(project_id: str) -> str | None:
    load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=True)
    base = os.getenv("PUBLIC_BACKEND_BASE_URL", settings.public_backend_base_url).rstrip("/")
    if not base:
        return None
    return f"{base}/download/{project_id}.zip"


def _fresh_build(build: ExtensionBuildRequest) -> ExtensionBuildRequest:
    """Use a unique output project for each extension generation."""
    return ExtensionBuildRequest(
        job_id=build.job_id,
        project_id=uuid4().hex,
        query=build.query,
        provider=build.provider,
        source=build.source,
        active_tabs=build.active_tabs,
    )


async def _stage_pause(seconds: float = 0.55) -> None:
    """Small UX delay so fast local steps still appear as a real pipeline."""
    await asyncio.sleep(seconds)


def _final_message(result: ExtensionBuildResult, spec: ExtensionSpec) -> str:
    name = spec.name or "Layer Extension"
    targets = ", ".join(spec.target_urls) or "the active tab"
    download = _download_url(result.project_id)

    step_lines = "\n".join(
        f"- **{step.agent_name}** — {step.summary}" for step in result.steps
    )

    if download:
        install_block = (
            "### Install in 3 steps\n\n"
            f"1. **Download** → [{name}.zip]({download})\n"
            "2. Open `chrome://extensions` and turn on **Developer mode** (top-right)\n"
            "3. Click **Load unpacked** and select the unzipped folder\n"
        )
    else:
        install_block = (
            "### Install in 3 steps\n\n"
            "1. Locate the generated extension folder on the host machine:\n"
            f"   `{result.package.extension_path}`\n"
            "2. Open `chrome://extensions` and turn on **Developer mode**\n"
            "3. Click **Load unpacked** and select that folder\n"
        )

    validation_line = (
        f"\n**Validation:** {result.validation.summary}\n" if result.validation else ""
    )

    return (
        f"**{name}** is ready to install.\n\n"
        f"### Built through Agentverse\n\n"
        f"{step_lines}\n"
        f"{validation_line}\n"
        f"{install_block}\n"
        f"_Active on:_ `{targets}`"
    )


async def run_orchestrator(build: ExtensionBuildRequest) -> ExtensionBuildResult:
    build = _fresh_build(build)
    await backend_client.ensure_project(build.project_id)

    architect = await run_architect(ArchitectRequest(build=build))
    rag = await run_rag(
        RagRequest(job_id=build.job_id, spec=architect.spec, query=build.query)
    )
    codegen = await run_codegen(
        CodegenRequest(job_id=build.job_id, build=build, spec=architect.spec, rag=rag)
    )
    validation = await run_validator(
        ValidationRequest(job_id=build.job_id, project_id=build.project_id)
    )
    package = await run_packager(
        PackageRequest(job_id=build.job_id, project_id=build.project_id)
    )

    steps = [
        _step("Architect", architect.summary, {"spec": architect.spec.dict()}),
        _step("RAG", rag.summary, {"snippets": rag.snippets}),
        _step("Codegen", codegen.summary, {"written_files": codegen.written_files}),
        _step("Validator", validation.summary, {"ok": validation.ok}),
        _step("Packager", package.summary, {"extension_path": package.extension_path}),
    ]
    result = ExtensionBuildResult(
        job_id=build.job_id,
        project_id=build.project_id,
        final_message="",
        steps=steps,
        validation=validation,
        package=package,
    )
    result.final_message = _final_message(result, architect.spec)
    return result


async def stream_orchestrator_events(
    build: ExtensionBuildRequest,
) -> AsyncGenerator[dict, None]:
    build = _fresh_build(build)
    await backend_client.ensure_project(build.project_id)

    yield {"type": "content", "content": "Agentverse Orchestrator: starting build.\n"}
    await _stage_pause(0.45)

    yield {"type": "tool_start", "name": "Agentverse Architect", "args": {}}
    await _stage_pause()
    architect = await run_architect(ArchitectRequest(build=build))
    yield {"type": "tool_end", "name": "Agentverse Architect"}
    yield _artifact_event(
        "architect",
        "Architect",
        "Spec drafted",
        architect.summary,
        meta=[
            {"label": "Extension", "value": architect.spec.name},
            {"label": "Targets", "value": ", ".join(architect.spec.target_urls)},
            {"label": "Files", "value": ", ".join(architect.spec.files_needed)},
        ],
        chips=architect.spec.verification_notes[:3],
    )
    await _stage_pause(0.25)
    yield {"type": "content", "content": f"{architect.summary}\n"}
    await _stage_pause(0.45)

    yield {"type": "tool_start", "name": "Agentverse RAG", "args": {}}
    await _stage_pause()
    rag = await run_rag(
        RagRequest(job_id=build.job_id, spec=architect.spec, query=build.query)
    )
    yield {"type": "tool_end", "name": "Agentverse RAG"}
    yield _artifact_event(
        "rag",
        "RAG",
        "Context assembled",
        rag.summary,
        meta=[
            {"label": "Patterns", "value": str(len(rag.snippets))},
            {"label": "Source", "value": "curated + site bootstrap"},
        ],
        chips=rag.snippets[:3],
    )
    await _stage_pause(0.25)
    yield {"type": "content", "content": f"{rag.summary}\n"}
    await _stage_pause(0.45)

    yield {"type": "tool_start", "name": "Agentverse Codegen", "args": {}}
    await _stage_pause()
    codegen = await run_codegen(
        CodegenRequest(job_id=build.job_id, build=build, spec=architect.spec, rag=rag)
    )
    yield {"type": "tool_end", "name": "Agentverse Codegen"}
    yield _artifact_event(
        "codegen",
        "Codegen",
        "Files written",
        codegen.summary,
        meta=[
            {"label": "Written", "value": f"{len(codegen.written_files)} files"},
            {"label": "Project", "value": codegen.project_id},
        ],
        chips=codegen.written_files,
    )
    await _stage_pause(0.25)
    yield {"type": "content", "content": f"{codegen.summary}\n"}
    await _stage_pause(0.45)

    yield {"type": "tool_start", "name": "Agentverse Validator", "args": {}}
    await _stage_pause()
    validation = await run_validator(
        ValidationRequest(job_id=build.job_id, project_id=build.project_id)
    )
    yield {"type": "tool_end", "name": "Agentverse Validator"}
    yield _artifact_event(
        "validator",
        "Validator",
        "Manifest checked",
        validation.summary,
        meta=[
            {"label": "Status", "value": "passed" if validation.ok else "needs fixes"},
            {"label": "Errors", "value": str(len(validation.errors))},
            {"label": "Warnings", "value": str(len(validation.warnings))},
        ],
        chips=[item.get("message", "") for item in (validation.errors + validation.warnings)[:3]],
    )
    await _stage_pause(0.25)
    yield {"type": "content", "content": f"{validation.summary}\n"}
    await _stage_pause(0.45)

    yield {"type": "tool_start", "name": "Agentverse Packager", "args": {}}
    await _stage_pause()
    package = await run_packager(
        PackageRequest(job_id=build.job_id, project_id=build.project_id)
    )
    yield {"type": "tool_end", "name": "Agentverse Packager"}
    yield _artifact_event(
        "packager",
        "Packager",
        "Install package ready",
        package.summary,
        meta=[
            {"label": "Folder", "value": os.path.basename(package.extension_path)},
            {"label": "ZIP", "value": os.path.basename(package.zip_path) if package.zip_path else "not generated"},
        ],
        chips=["Load unpacked in Chrome", package.extension_path],
    )
    await _stage_pause(0.25)
    yield {"type": "content", "content": f"{package.summary}\n"}
    yield {
        "type": "extension_ready",
        "path": package.extension_path,
        "project_id": build.project_id,
    }

    result = ExtensionBuildResult(
        job_id=build.job_id,
        project_id=build.project_id,
        final_message="",
        steps=[
            _step("Architect", architect.summary),
            _step("RAG", rag.summary),
            _step("Codegen", codegen.summary),
            _step("Validator", validation.summary),
            _step("Packager", package.summary),
        ],
        validation=validation,
        package=package,
    )
    result.final_message = _final_message(result, architect.spec)
    yield {"type": "content", "content": result.final_message}
