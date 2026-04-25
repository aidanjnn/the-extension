import json
import re
from dataclasses import dataclass, field


REQUIRED_MANIFEST_FIELDS = {"manifest_version", "name", "version"}
DEPRECATED_MV2_APIS = [
    "chrome.extension.sendRequest",
    "chrome.extension.onRequest",
    "chrome.tabs.sendRequest",
    "chrome.tabs.getSelected",
    "chrome.browserAction",
    "chrome.pageAction",
    "chrome.background.getBackgroundPage",
    "webRequestBlocking",
]


@dataclass
class ValidatorResult:
    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def validate_extension(files: dict[str, str]) -> ValidatorResult:
    errors: list[str] = []
    warnings: list[str] = []

    # Layer 1: Manifest structure
    manifest_errors, manifest_warnings, manifest = _validate_manifest(files)
    errors.extend(manifest_errors)
    warnings.extend(manifest_warnings)

    # Layer 2: File references
    if manifest:
        ref_errors = _validate_file_references(files, manifest)
        errors.extend(ref_errors)

    # Layer 3: JS syntax
    js_errors, js_warnings = _validate_js_syntax(files)
    errors.extend(js_errors)
    warnings.extend(js_warnings)

    # Layer 4: MV3 compatibility
    mv3_warnings = _validate_mv3_compat(files)
    warnings.extend(mv3_warnings)

    return ValidatorResult(valid=len(errors) == 0, errors=errors, warnings=warnings)


def _validate_manifest(files: dict[str, str]) -> tuple[list, list, dict | None]:
    errors = []
    warnings = []

    if "manifest.json" not in files:
        return ["manifest.json is missing"], [], None

    try:
        manifest = json.loads(files["manifest.json"])
    except json.JSONDecodeError as e:
        return [f"manifest.json is not valid JSON: {e}"], [], None

    missing = REQUIRED_MANIFEST_FIELDS - set(manifest.keys())
    if missing:
        errors.append(f"manifest.json missing required fields: {', '.join(missing)}")

    if manifest.get("manifest_version") != 3:
        errors.append("manifest_version must be 3 (MV3)")

    return errors, warnings, manifest


def _validate_file_references(files: dict[str, str], manifest: dict) -> list[str]:
    errors = []

    # Check content_scripts
    for cs in manifest.get("content_scripts", []):
        for js_file in cs.get("js", []):
            if js_file not in files:
                errors.append(f"content_scripts references missing file: {js_file}")
        for css_file in cs.get("css", []):
            if css_file not in files:
                errors.append(f"content_scripts references missing file: {css_file}")

    # Check popup
    action = manifest.get("action", {})
    popup = action.get("default_popup")
    if popup and popup not in files:
        errors.append(f"action.default_popup references missing file: {popup}")

    # Check background service worker
    bg = manifest.get("background", {})
    sw = bg.get("service_worker")
    if sw and sw not in files:
        errors.append(f"background.service_worker references missing file: {sw}")

    return errors


def _validate_js_syntax(files: dict[str, str]) -> tuple[list, list]:
    errors = []
    warnings = []

    js_files = {k: v for k, v in files.items() if k.endswith((".js", ".ts"))}
    for filename, content in js_files.items():
        # Check for unbalanced braces
        open_b = content.count("{")
        close_b = content.count("}")
        if open_b != close_b:
            warnings.append(
                f"{filename}: unbalanced braces ({{ {open_b} vs }} {close_b})"
            )

        # Check for syntax red flags
        if re.search(r"\beval\s*\(", content):
            warnings.append(f"{filename}: use of eval() detected (unsafe + MV3 restricted)")

    return errors, warnings


def _validate_mv3_compat(files: dict[str, str]) -> list[str]:
    warnings = []
    js_files = {k: v for k, v in files.items() if k.endswith((".js", ".ts"))}

    for filename, content in js_files.items():
        for api in DEPRECATED_MV2_APIS:
            if api in content:
                warnings.append(f"{filename}: deprecated MV2 API detected: {api}")

    return warnings
