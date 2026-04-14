import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class InstallResult:
    plugin_name: str
    plugin_source: str
    plugin_target: str
    marketplace_path: str
    link_action: str
    marketplace_action: str


def _load_plugin_name(plugin_source: Path) -> str:
    manifest_path = plugin_source / ".codex-plugin" / "plugin.json"
    if not manifest_path.exists():
        raise ValueError(f"plugin manifest not found: {manifest_path}")
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid plugin manifest json: {manifest_path}") from exc
    name = str(data.get("name") or "").strip()
    if not name:
        raise ValueError(f"plugin manifest missing name: {manifest_path}")
    return name


def _ensure_plugin_link(plugin_source: Path, plugins_home: Path, plugin_name: str) -> tuple[Path, str]:
    plugins_home.mkdir(parents=True, exist_ok=True)
    target = plugins_home / plugin_name
    source_resolved = plugin_source.resolve()

    if target.exists() or target.is_symlink():
        if target.is_symlink():
            current = target.resolve()
            if current == source_resolved:
                return target, "kept_existing_symlink"
            raise ValueError(
                f"plugin target already points elsewhere: {target} -> {current}. "
                "remove it manually or choose another plugins-home."
            )
        raise ValueError(
            f"plugin target already exists and is not a symlink: {target}. "
            "move/remove it manually before install."
        )

    target.symlink_to(source_resolved, target_is_directory=True)
    return target, "created_symlink"


def _default_marketplace() -> dict:
    return {
        "name": "local-marketplace",
        "interface": {"displayName": "Local Plugins"},
        "plugins": [],
    }


def _upsert_marketplace_entry(marketplace_path: Path, plugin_name: str) -> str:
    marketplace_path.parent.mkdir(parents=True, exist_ok=True)
    if marketplace_path.exists():
        try:
            data = json.loads(marketplace_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid marketplace json: {marketplace_path}") from exc
    else:
        data = _default_marketplace()

    if not isinstance(data, dict):
        raise ValueError(f"invalid marketplace shape: {marketplace_path}")

    if not isinstance(data.get("interface"), dict):
        data["interface"] = {"displayName": "Local Plugins"}
    if not data.get("name"):
        data["name"] = "local-marketplace"

    plugins = data.get("plugins")
    if not isinstance(plugins, list):
        plugins = []
        data["plugins"] = plugins

    entry = {
        "name": plugin_name,
        "source": {
            "source": "local",
            "path": f"./plugins/{plugin_name}",
        },
        "policy": {
            "installation": "AVAILABLE",
            "authentication": "ON_INSTALL",
        },
        "category": "Productivity",
    }

    action = "appended"
    replaced = False
    for idx, existing in enumerate(plugins):
        if isinstance(existing, dict) and existing.get("name") == plugin_name:
            plugins[idx] = entry
            replaced = True
            action = "updated_existing"
            break
    if not replaced:
        plugins.append(entry)

    marketplace_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return action


def install_home_plugin(
    plugin_source: str,
    plugins_home: str = "~/plugins",
    marketplace_path: str = "~/.agents/plugins/marketplace.json",
) -> InstallResult:
    source = Path(plugin_source).expanduser().resolve()
    if not source.exists():
        raise ValueError(f"plugin source does not exist: {source}")

    plugin_name = _load_plugin_name(source)
    target, link_action = _ensure_plugin_link(source, Path(plugins_home).expanduser(), plugin_name)
    m_action = _upsert_marketplace_entry(Path(marketplace_path).expanduser(), plugin_name)

    return InstallResult(
        plugin_name=plugin_name,
        plugin_source=str(source),
        plugin_target=str(target),
        marketplace_path=str(Path(marketplace_path).expanduser()),
        link_action=link_action,
        marketplace_action=m_action,
    )
