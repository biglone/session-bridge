import json
from pathlib import Path

from codex_session_bridge.installer import install_home_plugin


def _write_plugin_manifest(plugin_root: Path, plugin_name: str) -> None:
    manifest = plugin_root / ".codex-plugin" / "plugin.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps({"name": plugin_name}, indent=2), encoding="utf-8")


def test_install_home_plugin_creates_symlink_and_marketplace(tmp_path: Path) -> None:
    source = tmp_path / "plugin-src"
    plugins_home = tmp_path / "plugins-home"
    marketplace = tmp_path / ".agents" / "plugins" / "marketplace.json"
    _write_plugin_manifest(source, "bridge-plugin")

    result = install_home_plugin(
        plugin_source=str(source),
        plugins_home=str(plugins_home),
        marketplace_path=str(marketplace),
    )

    target = plugins_home / "bridge-plugin"
    assert result.plugin_name == "bridge-plugin"
    assert target.is_symlink()
    assert target.resolve() == source.resolve()

    data = json.loads(marketplace.read_text(encoding="utf-8"))
    assert data["plugins"][0]["name"] == "bridge-plugin"
    assert data["plugins"][0]["source"]["path"] == "./plugins/bridge-plugin"


def test_install_home_plugin_updates_existing_marketplace_entry(tmp_path: Path) -> None:
    source = tmp_path / "plugin-src"
    plugins_home = tmp_path / "plugins-home"
    marketplace = tmp_path / ".agents" / "plugins" / "marketplace.json"
    _write_plugin_manifest(source, "bridge-plugin")

    marketplace.parent.mkdir(parents=True, exist_ok=True)
    marketplace.write_text(
        json.dumps(
            {
                "name": "local-marketplace",
                "interface": {"displayName": "Local Plugins"},
                "plugins": [
                    {
                        "name": "bridge-plugin",
                        "source": {"source": "local", "path": "./plugins/old-name"},
                        "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
                        "category": "Productivity",
                    }
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    result = install_home_plugin(
        plugin_source=str(source),
        plugins_home=str(plugins_home),
        marketplace_path=str(marketplace),
    )
    assert result.marketplace_action == "updated_existing"

    data = json.loads(marketplace.read_text(encoding="utf-8"))
    assert len(data["plugins"]) == 1
    assert data["plugins"][0]["source"]["path"] == "./plugins/bridge-plugin"
