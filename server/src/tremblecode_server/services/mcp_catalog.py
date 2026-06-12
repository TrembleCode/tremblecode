from functools import lru_cache

import yaml

from ..config import get_settings


@lru_cache
def load_catalog() -> dict[str, dict]:
    path = get_settings().templates_dir / "mcp_catalog.yaml"
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text()) or {}
    return data.get("servers", {})


def catalog_entry(name: str) -> dict | None:
    return load_catalog().get(name)


def catalog_for_prompt() -> str:
    """Catalog rendered for the lead's planning instructions."""
    lines = []
    for name, entry in load_catalog().items():
        env = f" (needs: {', '.join(entry['env_keys'])})" if entry.get("env_keys") else ""
        lines.append(f"- `{name}`: {entry['description']}{env}")
    return "\n".join(lines)
