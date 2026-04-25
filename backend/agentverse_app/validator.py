"""Extension Validator Agent role."""

from __future__ import annotations

from agentverse_app import backend_client
from agentverse_app.messages import ValidationRequest, ValidationResult


async def run_validator(request: ValidationRequest) -> ValidationResult:
    report = await backend_client.validate(request.project_id)
    return ValidationResult(
        job_id=request.job_id,
        project_id=request.project_id,
        ok=bool(report.get("ok")),
        errors=report.get("errors", []),
        warnings=report.get("warnings", []),
        summary=report.get("summary", "Validation completed."),
    )
