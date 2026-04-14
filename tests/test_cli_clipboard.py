from codex_session_bridge import cli


def test_copy_to_clipboard_uses_osc52_fallback_when_no_native_tool(monkeypatch) -> None:
    monkeypatch.setattr(cli.shutil, "which", lambda _: None)
    monkeypatch.setattr(cli, "_copy_via_osc52", lambda _: True)

    copied, method = cli._copy_to_clipboard("hello")

    assert copied is True
    assert method == "osc52"


def test_copy_to_clipboard_reports_failure_when_all_methods_fail(monkeypatch) -> None:
    monkeypatch.setattr(cli.shutil, "which", lambda _: None)
    monkeypatch.setattr(cli, "_copy_via_osc52", lambda _: False)

    copied, method = cli._copy_to_clipboard("hello")

    assert copied is False
    assert method == ""
