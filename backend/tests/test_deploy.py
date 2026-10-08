"""Checks on the shipped compose file (no YAML parser is a runtime dependency, so read the service blocks as text)."""

import re
from pathlib import Path

COMPOSE = Path(__file__).resolve().parents[2] / "deploy" / "compose.yaml"


def service_block(name: str) -> str:
    text = COMPOSE.read_text(encoding="utf-8")
    match = re.search(rf"^  {name}:\n(.*?)(?=^  \S|^\S|\Z)", text, re.M | re.S)
    assert match, f"service {name} missing"
    return match.group(1)


def test_worker_does_not_inherit_the_api_http_healthcheck():
    """The image's HEALTHCHECK probes the API port; the worker serves no HTTP and would be reported unhealthy."""
    assert re.search(r"healthcheck:\n\s+disable: true", service_block("worker"))
