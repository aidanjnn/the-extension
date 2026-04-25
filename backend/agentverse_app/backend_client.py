"""HTTP client for Agentverse agents calling the FastAPI execution API."""

from __future__ import annotations

import httpx

from agentverse_app.config import settings


def _url(path: str) -> str:
    return settings.backend_execution_api_url.rstrip("/") + path


def _headers() -> dict[str, str]:
    return {"x-agentverse-token": settings.execution_api_token}


async def ensure_project(project_id: str, name: str = "Agentverse Extension") -> dict:
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            _url("/internal/agentverse/projects"),
            headers=_headers(),
            json={"project_id": project_id, "name": name},
        )
        response.raise_for_status()
        return response.json()


async def write_files(project_id: str, files: dict[str, str]) -> dict:
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            _url(f"/internal/agentverse/projects/{project_id}/files"),
            headers=_headers(),
            json={"files": files},
        )
        response.raise_for_status()
        return response.json()


async def read_files(project_id: str) -> dict:
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(
            _url(f"/internal/agentverse/projects/{project_id}/files"),
            headers=_headers(),
        )
        response.raise_for_status()
        return response.json()


async def validate(project_id: str) -> dict:
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            _url(f"/internal/agentverse/projects/{project_id}/validate"),
            headers=_headers(),
        )
        response.raise_for_status()
        return response.json()


async def package(project_id: str) -> dict:
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            _url(f"/internal/agentverse/projects/{project_id}/package"),
            headers=_headers(),
        )
        response.raise_for_status()
        return response.json()


async def load_info(project_id: str) -> dict:
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            _url(f"/internal/agentverse/projects/{project_id}/load-info"),
            headers=_headers(),
        )
        response.raise_for_status()
        return response.json()
