from uagents import Model


class ExtensionRequest(Model):
    prompt: str
    browser_context: str | None = None
    project_id: str | None = None


class CodeGenRequest(Model):
    prompt: str
    project_id: str
    browser_context: str | None = None
    fix_errors: list[str] | None = None


class CodeGenResponse(Model):
    files: dict[str, str]
    success: bool
    error: str | None = None


class ValidateRequest(Model):
    files: dict[str, str]


class ValidateResponse(Model):
    valid: bool
    errors: list[str]
    warnings: list[str]


class ExtensionResponse(Model):
    files: dict[str, str]
    valid: bool
    summary: str
