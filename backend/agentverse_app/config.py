"""Configuration for Agentverse agents and backend bridge."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=True)


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default)


@dataclass(frozen=True)
class AgentverseSettings:
    agentverse_api_key: str = _env("AGENTVERSE_API_KEY")
    asi_one_api_key: str = _env("ASI_ONE_API_KEY")
    public_agent_base_url: str = _env("PUBLIC_AGENT_BASE_URL")
    public_backend_base_url: str = _env("PUBLIC_BACKEND_BASE_URL")
    backend_execution_api_url: str = _env(
        "BACKEND_EXECUTION_API_URL",
        "http://localhost:8000",
    )
    uagents_port: int = int(_env("UAGENTS_PORT", "8001"))
    execution_api_token: str = _env("AGENTVERSE_EXECUTION_TOKEN", "dev-agentverse-token")
    orchestrator_seed: str = _env(
        "ORCHESTRATOR_SEED",
        "browser-forge-orchestrator-demo-seed",
    )
    architect_seed: str = _env("ARCHITECT_SEED", "browser-forge-architect-demo-seed")
    rag_seed: str = _env("RAG_SEED", "browser-forge-rag-demo-seed")
    codegen_seed: str = _env("CODEGEN_SEED", "browser-forge-codegen-demo-seed")
    validator_seed: str = _env("VALIDATOR_SEED", "browser-forge-validator-demo-seed")
    packager_seed: str = _env("PACKAGER_SEED", "browser-forge-packager-demo-seed")
    architect_address: str = _env("ARCHITECT_AGENT_ADDRESS")
    rag_address: str = _env("RAG_AGENT_ADDRESS")
    codegen_address: str = _env("CODEGEN_AGENT_ADDRESS")
    validator_address: str = _env("VALIDATOR_AGENT_ADDRESS")
    packager_address: str = _env("PACKAGER_AGENT_ADDRESS")
    demo_mode: bool = _env("AGENTVERSE_DEMO_MODE", "true").lower() == "true"
    enable_graph_rag: bool = _env("ENABLE_GRAPH_RAG", "false").lower() == "true"


settings = AgentverseSettings()
