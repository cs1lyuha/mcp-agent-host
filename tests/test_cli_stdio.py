"""Demo-ul complet, cu serverul de exemplu pornit ca proces separat pe stdio."""

from host.__main__ import load_config, main


def test_config_resolves_python_and_cwd():
    cfg = load_config("examples/servers.json")
    assert "notes" in cfg and cfg["notes"].args == ["examples/notes_server.py"]


def test_demo_with_approval(capsys):
    assert main(["demo"]) == 0
    out = capsys.readouterr().out
    assert "delete_note*" in out and "Am șters notița expirată." in out


def test_demo_with_denial(capsys):
    main(["demo", "--deny"])
    out = capsys.readouterr().out
    assert "denied" in out and "nu a aprobat" in out
