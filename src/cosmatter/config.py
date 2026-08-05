"""Safe, dependency-free configuration loading for CosMatter."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


AGENT_ROOT = Path(__file__).resolve().parents[2]
# The workspace-level file is intentionally read-only and Git-ignored.  Keep secrets
# outside the distributable CosMatter package tree.
DEFAULT_ENV_FILE = AGENT_ROOT.parent / ".env"


def _read_dotenv(path: Path) -> dict[str, str]:
    """Read a simple dotenv file without printing or exporting its values."""
    if not path.is_file():
        return {}
    result: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", maxsplit=1)
        key = key.strip()
        if key:
            result[key] = value.strip().strip('"').strip("'")
    return result


def _positive_int(value: str | None, default: int) -> int:
    try:
        parsed = int(value or default)
    except ValueError:
        return default
    return parsed if parsed > 0 else default


@dataclass(frozen=True)
class Settings:
    llm_provider: str | None
    llm_model: str | None
    llm_base_url: str
    deepseek_api_key: str | None
    llm_thinking_enabled: bool
    llm_reasoning_effort: str | None
    deepseek_configured: bool
    sciverse_api_token: str | None
    sciverse_base_url: str
    mineru_api_token: str | None
    mineru_base_url: str
    mineru_model_version: str
    openalex_api_key: str | None
    openalex_base_url: str
    crossref_mailto: str | None
    crossref_base_url: str
    http_timeout_seconds: int
    api_max_retries: int

    @property
    def sciverse_configured(self) -> bool:
        return bool(self.sciverse_api_token)

    @classmethod
    def load(cls, environ: Mapping[str, str] | None = None) -> "Settings":
        runtime_environ = dict(os.environ if environ is None else environ)
        values: dict[str, str] = {}
        # An explicit mapping is a hermetic override used by tests and callers.
        # An explicit env-file path also prevents any read of the protected
        # workspace file, which makes isolated service tests secret-free.
        explicit_env_file = runtime_environ.get("COSMATTER_ENV_FILE")
        if environ is None and not explicit_env_file:
            values.update(_read_dotenv(DEFAULT_ENV_FILE))
        if explicit_env_file:
            values.update(_read_dotenv(Path(explicit_env_file)))
        values.update(runtime_environ)
        token = values.get("SCIVERSE_API_TOKEN") or values.get("SCIVERSE_API_KEY")
        deepseek_key = values.get("DEEPSEEK_API_KEY", "").strip()
        mineru_token = values.get("MINERU_API_TOKEN", "").strip()
        openalex_key = values.get("OPENALEX_API_KEY", "").strip()
        crossref_mailto = values.get("CROSSREF_MAILTO", "").strip()
        return cls(
            llm_provider=values.get("LLM_PROVIDER") or None,
            llm_model=values.get("LLM_MODEL") or None,
            llm_base_url=(values.get("LLM_BASE_URL") or "https://api.deepseek.com").rstrip("/"),
            deepseek_api_key=deepseek_key or None,
            llm_thinking_enabled=values.get("LLM_THINKING_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"},
            llm_reasoning_effort=values.get("LLM_REASONING_EFFORT") or None,
            deepseek_configured=bool(deepseek_key),
            sciverse_api_token=token.strip() if token else None,
            sciverse_base_url=(values.get("SCIVERSE_BASE_URL") or "https://api.sciverse.space").rstrip("/"),
            mineru_api_token=mineru_token or None,
            mineru_base_url=(values.get("MINERU_BASE_URL") or "https://mineru.net").rstrip("/"),
            mineru_model_version=(values.get("MINERU_MODEL_VERSION") or "vlm").strip(),
            openalex_api_key=openalex_key or None,
            openalex_base_url=(values.get("OPENALEX_BASE_URL") or "https://api.openalex.org").rstrip("/"),
            crossref_mailto=crossref_mailto or None,
            crossref_base_url=(values.get("CROSSREF_BASE_URL") or "https://api.crossref.org").rstrip("/"),
            http_timeout_seconds=_positive_int(values.get("HTTP_TIMEOUT_SECONDS"), 60),
            api_max_retries=_positive_int(values.get("API_MAX_RETRIES"), 3),
        )

    def status(self) -> dict[str, object]:
        """Return diagnostic booleans only; secrets are never represented here."""
        return {
            "llm_provider": self.llm_provider,
            "llm_model": self.llm_model,
            "llm_base_url": self.llm_base_url,
            "llm_thinking_enabled": self.llm_thinking_enabled,
            "llm_reasoning_effort": self.llm_reasoning_effort,
            "deepseek_configured": self.deepseek_configured,
            "sciverse_configured": self.sciverse_configured,
            "sciverse_base_url": self.sciverse_base_url,
            "mineru_configured": bool(self.mineru_api_token),
            "mineru_base_url": self.mineru_base_url,
            "mineru_model_version": self.mineru_model_version,
            "openalex_configured": bool(self.openalex_api_key),
            "openalex_base_url": self.openalex_base_url,
            "crossref_polite_contact_configured": bool(self.crossref_mailto),
            "crossref_base_url": self.crossref_base_url,
            "http_timeout_seconds": self.http_timeout_seconds,
            "api_max_retries": self.api_max_retries,
        }
