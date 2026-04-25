"""Register Browser Forge agents on Agentverse.

Run after the agents are reachable from the public endpoint configured in
PUBLIC_AGENT_BASE_URL:
    uv run python -m agentverse_app.register
"""

from __future__ import annotations

from uagents_core.utils.registration import (
    AgentverseRequestError,
    RegistrationRequestCredentials,
    register_chat_agent,
)

from agentverse_app.config import settings


AGENT_PROFILES = [
    {
        "name": "Browser Orchestrator",
        "seed": settings.orchestrator_seed,
        "path": "/submit",
        "readme": (
            "# Browser Orchestrator\n\n"
            "Coordinates specialist agents that turn browser customization intent "
            "into generated, validated Chrome extensions."
        ),
        "categories": ["chrome extension", "browser automation", "ai coding agent"],
    },
    {
        "name": "Extension Architect",
        "seed": settings.architect_seed,
        "path": "/submit",
        "readme": "# Extension Architect\n\nPlans Manifest V3 Chrome extensions from user intent.",
        "categories": ["software design", "manifest v3", "chrome extension"],
    },
    {
        "name": "Extension RAG",
        "seed": settings.rag_seed,
        "path": "/submit",
        "readme": "# Extension RAG\n\nRetrieves reference patterns for browser extension generation.",
        "categories": ["code search", "reference retrieval", "browser extension patterns"],
    },
    {
        "name": "Extension Codegen",
        "seed": settings.codegen_seed,
        "path": "/submit",
        "readme": "# Extension Codegen\n\nGenerates Chrome extension files and writes them through the backend execution API.",
        "categories": ["code generation", "javascript", "chrome extension"],
    },
    {
        "name": "Extension Validator",
        "seed": settings.validator_seed,
        "path": "/submit",
        "readme": "# Extension Validator\n\nValidates generated Manifest V3 Chrome extensions.",
        "categories": ["manifest v3 validation", "static analysis", "extension testing"],
    },
    {
        "name": "Extension Packager",
        "seed": settings.packager_seed,
        "path": "/submit",
        "readme": "# Extension Packager\n\nPackages generated extensions and returns load instructions.",
        "categories": ["artifact packaging", "load unpacked", "extension delivery"],
    },
]


def main() -> None:
    if not settings.agentverse_api_key:
        raise RuntimeError("AGENTVERSE_API_KEY is required to register agents.")
    if not settings.public_agent_base_url:
        raise RuntimeError("PUBLIC_AGENT_BASE_URL is required to register agents.")

    for profile in AGENT_PROFILES:
        credentials = RegistrationRequestCredentials(
            agent_seed_phrase=profile["seed"],
            agentverse_api_key=settings.agentverse_api_key,
        )
        endpoint = settings.public_agent_base_url.rstrip("/") + profile["path"]
        try:
            register_chat_agent(
                name=profile["name"],
                endpoint=endpoint,
                active=True,
                credentials=credentials,
                readme=profile["readme"],
                metadata={
                    "categories": profile["categories"],
                    "is_public": "True",
                },
            )
            print(f"Registered {profile['name']}: {endpoint}")
        except AgentverseRequestError as error:
            print(f"Failed to register {profile['name']}: {error}")
            if error.from_exc:
                print(f"Caused by: {error.from_exc}")


if __name__ == "__main__":
    main()
