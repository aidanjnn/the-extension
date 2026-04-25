"""Typed Agentverse message contracts for extension-building agents."""

from __future__ import annotations

from typing import Any, Literal

from uagents import Model


class ExtensionBuildRequest(Model):
    job_id: str
    project_id: str
    query: str
    provider: str = "gemini"
    source: Literal["asi_one", "sidepanel", "local"] = "local"
    active_tabs: list[dict[str, Any]] = []


class ExtensionSpec(Model):
    job_id: str
    project_id: str
    name: str
    description: str
    target_urls: list[str]
    files_needed: list[str]
    behavior: str
    verification_notes: list[str] = []


class ArchitectRequest(Model):
    build: ExtensionBuildRequest


class ArchitectResult(Model):
    job_id: str
    spec: ExtensionSpec
    summary: str


class RagRequest(Model):
    job_id: str
    spec: ExtensionSpec
    query: str


class RagResult(Model):
    job_id: str
    snippets: list[str]
    summary: str


class CodegenRequest(Model):
    job_id: str
    build: ExtensionBuildRequest
    spec: ExtensionSpec
    rag: RagResult


class CodegenResult(Model):
    job_id: str
    project_id: str
    files: dict[str, str]
    written_files: list[str] = []
    summary: str


class ValidationRequest(Model):
    job_id: str
    project_id: str


class ValidationResult(Model):
    job_id: str
    project_id: str
    ok: bool
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    summary: str


class PackageRequest(Model):
    job_id: str
    project_id: str


class PackageResult(Model):
    job_id: str
    project_id: str
    extension_path: str
    zip_path: str = ""
    load_instructions: str
    summary: str


class AgentStepResult(Model):
    agent_name: str
    status: Literal["ok", "error"]
    summary: str
    payload: dict[str, Any] = {}


class ExtensionBuildResult(Model):
    job_id: str
    project_id: str
    final_message: str
    steps: list[AgentStepResult]
    validation: ValidationResult
    package: PackageResult
