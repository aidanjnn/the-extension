"""Extension Packager Agent role."""

from __future__ import annotations

from agentverse_app import backend_client
from agentverse_app.messages import PackageRequest, PackageResult


async def run_packager(request: PackageRequest) -> PackageResult:
    package = await backend_client.package(request.project_id)
    return PackageResult(
        job_id=request.job_id,
        project_id=request.project_id,
        extension_path=package.get("extension_path", ""),
        zip_path=package.get("zip_path", ""),
        load_instructions=package.get("load_instructions", ""),
        summary="Packaged extension and prepared Chrome load instructions.",
    )
