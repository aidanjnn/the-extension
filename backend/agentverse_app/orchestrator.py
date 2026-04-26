"""Agentverse Orchestrator role and local bridge helpers."""

from __future__ import annotations

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


def _final_message(result: ExtensionBuildResult, spec: ExtensionSpec) -> str:
    name = spec.name or "Browser Forge Extension"
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

    yield {"type": "tool_start", "name": "Agentverse Architect", "args": {}}
    architect = await run_architect(ArchitectRequest(build=build))
    yield {"type": "tool_end", "name": "Agentverse Architect"}
    yield {"type": "content", "content": f"{architect.summary}\n"}

    yield {"type": "tool_start", "name": "Agentverse RAG", "args": {}}
    rag = await run_rag(
        RagRequest(job_id=build.job_id, spec=architect.spec, query=build.query)
    )
    yield {"type": "tool_end", "name": "Agentverse RAG"}
    yield {"type": "content", "content": f"{rag.summary}\n"}

    yield {"type": "tool_start", "name": "Agentverse Codegen", "args": {}}
    codegen = await run_codegen(
        CodegenRequest(job_id=build.job_id, build=build, spec=architect.spec, rag=rag)
    )
    yield {"type": "tool_end", "name": "Agentverse Codegen"}
    yield {"type": "content", "content": f"{codegen.summary}\n"}

    yield {"type": "tool_start", "name": "Agentverse Validator", "args": {}}
    validation = await run_validator(
        ValidationRequest(job_id=build.job_id, project_id=build.project_id)
    )
    yield {"type": "tool_end", "name": "Agentverse Validator"}
    yield {"type": "content", "content": f"{validation.summary}\n"}

    yield {"type": "tool_start", "name": "Agentverse Packager", "args": {}}
    package = await run_packager(
        PackageRequest(job_id=build.job_id, project_id=build.project_id)
    )
    yield {"type": "tool_end", "name": "Agentverse Packager"}
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
