"""Operator-controlled configuration for the gateway and detectors."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Rule:
    id: str
    pattern: str


@dataclass(frozen=True)
class Settings:
    rules: tuple[Rule, ...]
    semantic_enabled: bool
    semantic_model: str
    semantic_threshold: float
    semantic_examples: tuple[str, ...]
    max_chars: int
    protected_roles: frozenset[str]
    audit_db: Path
    audit_token: str
    provider: str
    upstream_model: str
    ollama_base_url: str


def load_settings(path: str | Path | None = None) -> Settings:
    config_path = Path(path or os.getenv("PROMPT_SENTINEL_CONFIG", PROJECT_ROOT / "config.yaml"))
    with config_path.open("r", encoding="utf-8") as stream:
        data = yaml.safe_load(stream) or {}
    detector = data["detector"]
    semantic = detector["semantic"]
    rules = tuple(Rule(str(item["id"]), str(item["pattern"])) for item in detector["rules"])
    if len({rule.id for rule in rules}) != len(rules):
        raise ValueError("Rule IDs must be unique")
    for rule in rules:
        re.compile(rule.pattern)
    threshold = float(semantic["threshold"])
    if not 0 <= threshold <= 1:
        raise ValueError("Semantic threshold must be between 0 and 1")
    max_chars = int(detector["max_chars"])
    if max_chars < 1:
        raise ValueError("max_chars must be positive")
    roles = frozenset(str(role) for role in detector["protected_roles"])
    if not roles or not roles.issubset({"user", "tool"}):
        raise ValueError("protected_roles must contain user and/or tool")
    provider = os.getenv("UPSTREAM_PROVIDER", "ollama").lower()
    if provider not in {"ollama", "deepseek"}:
        raise ValueError("UPSTREAM_PROVIDER must be ollama or deepseek")
    audit_db = Path(os.getenv("PROMPT_SENTINEL_AUDIT_DB", PROJECT_ROOT / "data/audit.db"))
    if not audit_db.is_absolute():
        audit_db = PROJECT_ROOT / audit_db
    return Settings(
        rules=rules,
        semantic_enabled=bool(semantic["enabled"]),
        semantic_model=str(semantic["model"]),
        semantic_threshold=threshold,
        semantic_examples=tuple(str(example) for example in semantic["examples"]),
        max_chars=max_chars,
        protected_roles=roles,
        audit_db=audit_db,
        audit_token=os.getenv("PROMPT_SENTINEL_AUDIT_TOKEN", ""),
        provider=provider,
        upstream_model=os.getenv("UPSTREAM_MODEL", "llama3.2" if provider == "ollama" else "deepseek-chat"),
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/"),
    )
