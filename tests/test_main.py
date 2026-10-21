import pytest

from nexus_router import main


def test_missing_config_exits_nonzero(tmp_path, capsys):
    with pytest.raises(SystemExit) as e:
        main.router_main(["--config", str(tmp_path / "nope.yaml")])
    assert e.value.code != 0
    assert "nope.yaml" in capsys.readouterr().err


def test_invalid_config_prints_config_error(tmp_path, capsys):
    path = tmp_path / "c.yaml"
    path.write_text("nodes:\n  - name: a\n")
    with pytest.raises(SystemExit) as e:
        main.router_main(["--config", str(path)])
    assert e.value.code != 0
    assert "ollama_url" in capsys.readouterr().err


def test_valid_config_serves_on_listen_address(tmp_path, monkeypatch):
    path = tmp_path / "c.yaml"
    path.write_text("listen: {host: 127.0.0.1, port: 12345}\nnodes:\n  - {name: a, ollama_url: 'http://a:1'}\n")
    calls = {}
    monkeypatch.setattr(main.uvicorn, "run", lambda app, **kw: calls.update(app=app, **kw))
    main.router_main(["--config", str(path)])
    assert (calls["host"], calls["port"]) == ("127.0.0.1", 12345)


async def test_poller_starts_and_stops_with_app(tmp_path):
    from conftest import make_config
    from nexus_router.proxy import create_app

    app = create_app(make_config())
    async with app.router.lifespan_context(app):
        assert app.state.poller._tasks
    assert not app.state.poller._tasks
