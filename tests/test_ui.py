"""验证绝区零一条龙编辑块、宿主资源和 wheel 分发。"""

import tomllib
from html.parser import HTMLParser
from pathlib import Path
from shutil import copy2, copytree
from zipfile import ZipFile

import pytest
from app.api import plugin_router
from app.api._config_editors import config_detail_ui
from app.api.scripts import router as scripts_router
from app.config import ConfigCollection, config_manager
from app.core import Config, Plugin
from app.core.i18n import I18nManager
from app.models.config import PluginRecord, PluginRegistryCollection
from app.models.schema import DeclarativeBlockOut, HostBlockOut, PluginBlockOut
from app.plugin.calls import CallGate
from app.plugin.frontend import MountedFrontend
from app.plugin.http import HttpRegistry
from app.plugin.types import PluginState
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

import zzzod_adapter
from zzzod_adapter.adapter import ZzzOdAdapter
from zzzod_adapter.config import ZzzOdConfig

PACKAGE = Path(zzzod_adapter.__file__).resolve().parent
SOURCE = Path(__file__).resolve().parents[1]
NAME = PACKAGE.name
PAGES = {"script", "user"}
LOCALES = ("zh-CN", "en-US", "ja-JP")


class PanelAssets(HTMLParser):
    def __init__(self):
        super().__init__()
        self.files = {"script-src": [], "style-src": []}

    def handle_starttag(self, tag, attrs):
        fields = dict(attrs)
        assert tag != "style"
        assert not any(name == "style" or name.startswith("on") for name in fields)
        if tag == "script":
            assert fields.get("type") != "module" and "crossorigin" not in fields
            assert fields["src"].startswith("./")
            if fields["src"] != "./_host/panel-sdk.js":
                assert "defer" in fields
            self.files["script-src"].append(fields["src"][2:])
        if tag == "link" and fields.get("rel") == "stylesheet":
            assert fields["href"].startswith("./")
            self.files["style-src"].append(fields["href"][2:])


@pytest.fixture
async def editor_host(monkeypatch):
    scripts = ConfigCollection.build([ZzzOdConfig])
    await scripts.activate()
    monkeypatch.setattr(Config, "ScriptConfig", scripts)
    monkeypatch.setitem(config_manager._collections, "ScriptConfig", scripts)

    registry = PluginRegistryCollection.build()
    await registry.activate()
    record_id = registry.add(
        PluginRecord,
        payload={"info": {"plugin_name": NAME, "state": PluginState.ENABLED}},
    )
    await registry.commit()
    record = registry[record_id]
    record._plugin_cls = ZzzOdAdapter
    record._plugin = ZzzOdAdapter()
    monkeypatch.setattr(Config, "plugin_registry", registry)
    monkeypatch.setattr(Plugin, "script_types", {record.uid: ZzzOdAdapter.decl})

    gate = CallGate()
    monkeypatch.setitem(Plugin._calls, record.uid, gate)
    frontend = MountedFrontend.load(
        PACKAGE, NAME, "ZzzOd", None, gate, block_pages=PAGES
    )
    assert frontend is not None
    assert frontend.diagnostics == []
    assert frontend.block_pages == PAGES

    app = FastAPI()
    app.include_router(plugin_router)
    http = HttpRegistry()
    monkeypatch.setattr(Plugin, "http", http)
    http.bind_app(app)
    http.mount(NAME, [], router=ZzzOdAdapter.api_router, frontend=frontend, gate=gate)
    app.include_router(scripts_router)
    return app, frontend


@pytest.mark.parametrize("page", sorted(PAGES))
async def test_built_panel_served_under_host_csp(editor_host, page):
    app, frontend = editor_host
    root = f"/api/plugin/{NAME}/ui/{frontend.revision}"
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(f"{root}/{page}.html")
        assert response.status_code == 200
        policy = dict(
            directive.split(" ", 1)
            for directive in response.headers["Content-Security-Policy"].split("; ")
        )
        assert policy["default-src"] == "'none'"
        assert policy["sandbox"] == "allow-scripts allow-forms"
        assert all(
            source.startswith(f"http://test{root}/")
            for source in policy["connect-src"].split()
        )
        assets = PanelAssets()
        assets.feed(response.text)
        assert assets.files == {
            "script-src": ["_host/panel-sdk.js", "assets/main.js"],
            "style-src": ["_host/panel-base.css", "assets/main.css"],
        }
        for directive, mime in (
            ("script-src", "text/javascript"),
            ("style-src", "text/css"),
        ):
            assert "'unsafe-inline'" not in policy[directive].split()
            for path in assets.files[directive]:
                target = f"http://test{root}/{path}"
                assert target in policy[directive].split()
                asset = await client.get(target)
                assert asset.status_code == 200
                assert asset.headers["Content-Type"].startswith(mime)


async def test_editor_blocks_and_scoped_routes(editor_host, tmp_path, monkeypatch):
    app, frontend = editor_host
    monkeypatch.chdir(tmp_path)
    installation = tmp_path.with_name(f"{tmp_path.name}-installation")
    (installation / "src").mkdir(parents=True)
    (installation / "OneDragon-Launcher.exe").touch()
    script_uid, script = await Config.add_script(
        "ZzzOd", payload={"Info": {"RootPath": str(installation)}}
    )
    script_id = str(script_uid)
    _, script_documents = await Config.get_script(script_id)
    assert config_detail_ui(script, script_documents).blocks == [
        DeclarativeBlockOut(groups=["Info"]),
        HostBlockOut(name="game_binding"),
        PluginBlockOut(
            pageId="script",
            fallbackGroups=["Game", "Run"],
            mount=frontend.surface_mount(name=NAME, page="script"),
        ),
    ]

    user_uid, user = await Config.add_user(script_id)
    user_id = str(user_uid)
    _, user_documents = await Config.get_user(script_id, user_id)
    ui = config_detail_ui(user, user_documents)
    assert ui.blocks == [
        HostBlockOut(name="config_restore"),
        HostBlockOut(name="native_session"),
        DeclarativeBlockOut(groups=["Info"]),
        PluginBlockOut(
            pageId="user",
            fallbackGroups=["Game", "OneDragon"],
            mount=frontend.surface_mount(name=NAME, page="user"),
        ),
        DeclarativeBlockOut(groups=["Notify"]),
        HostBlockOut(name="webhooks"),
    ]
    assert [(pool.key, pool.kind) for pool in ui.backupTargets] == [
        ("mas", "user"),
        ("onedragon", "script"),
    ]
    assert ui.nativeSession == "config"
    for pool in ui.backupTargets:
        assert (await Config.list_config_backups(script_id, user_id, pool.key))[
            "items"
        ] == []

    ids = {"scriptId": script_id, "userId": user_id}
    prefix = f"/api/plugin/{NAME}"
    headers = {
        "X-Plugin-Ui-Provider": NAME,
        "X-Plugin-Ui-Activation": frontend.activation_id,
        "X-Plugin-Ui-Page": "user",
    }
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        for route in ("/api/scripts", prefix):
            launchers = await client.get(
                f"{route}/zzzod/launchers",
                params={"scriptId": script_id},
                headers=headers,
            )
            assert launchers.status_code == launchers.json()["code"] == 200, (
                launchers.text
            )
            assert launchers.json()["original_available"] is True

        edit_script = await client.get(
            f"{prefix}/editor/script/{script_id}", headers=headers
        )
        assert edit_script.json() == {
            "rootPath": str(installation),
            "users": [{"value": user_id, "label": user.Info.Name}],
        }

        edit_user = await client.get(
            f"{prefix}/editor/user/{script_id}/{user_id}", headers=headers
        )
        assert edit_user.json() == {
            "rootPath": str(installation),
            "base": "independent",
        }

        result = await client.post(
            "/api/scripts/user/update",
            json={**ids, "data": {"Info": {"Base": "native"}}},
        )
        assert result.status_code == result.json()["code"] == 200, result.text
        assert user.Info.IfQuickConfig is False
        assert (
            await client.get(
                f"{prefix}/editor/user/{script_id}/{user_id}", headers=headers
            )
        ).json()["base"] == "native"

        result = await client.post(
            "/api/scripts/update",
            headers={**headers, "X-Plugin-Ui-Page": "script"},
            json={"scriptId": script_id, "data": {"Run": {"RunTimesLimit": 2}}},
        )
        assert result.status_code == result.json()["code"] == 200, result.text
        assert script.Run.RunTimesLimit == 2

        result = await client.post(
            "/api/scripts/user/update",
            json={**ids, "data": {"Info": {"Base": "independent"}}},
        )
        assert result.status_code == result.json()["code"] == 200, result.text
        result = await client.post(
            "/api/scripts/user/update",
            headers=headers,
            json={**ids, "data": {"OneDragon": {"AfterDone": "无"}}},
        )
        assert result.status_code == result.json()["code"] == 200, result.text
        assert user.Info.Base == "independent"
        assert user.OneDragon.AfterDone == "无"

    assert not any(
        route.include_in_schema
        for route in ZzzOdAdapter.api_router.routes
        if route.path.startswith(prefix)
    )


async def test_panel_translations_use_plugin_namespace():
    manager = I18nManager(Config.resource_path / "i18n")
    manager.set_package_roots({NAME: PACKAGE})
    for locale in LOCALES:
        messages, _ = await manager.get_messages(locale)
        panel = messages["plugins"][NAME]["panel"]
        assert (
            panel["slotsManage"] and panel["predefinedTeams"] and panel["quickImport"]
        )


def test_wheel_contains_ui_and_locales(tmp_path, monkeypatch):
    from setuptools.build_meta import build_wheel

    sources = tmp_path / "sources"
    sources.mkdir()
    for filename in ("pyproject.toml", "README.md", "LICENSE"):
        copy2(SOURCE / filename, sources)
    copytree(PACKAGE, sources / "src" / NAME)
    monkeypatch.chdir(sources)
    metadata = tomllib.loads((sources / "pyproject.toml").read_text(encoding="utf-8"))
    assert f"auto-mas-id:{NAME}" in metadata["project"]["keywords"]
    wheel = tmp_path / build_wheel(str(tmp_path))
    with ZipFile(wheel) as archive:
        paths = {
            f"{NAME}/ui/manifest.json",
            f"{NAME}/ui/script.html",
            f"{NAME}/ui/user.html",
            f"{NAME}/ui/assets/main.js",
            f"{NAME}/ui/assets/main.css",
            *(f"{NAME}/i18n/{locale}.json" for locale in LOCALES),
        }
        assets = {
            path.relative_to(sources / "src").as_posix()
            for folder in ("ui", "i18n")
            for path in (sources / "src" / NAME / folder).rglob("*")
            if path.is_file()
        }
        assert paths <= assets <= set(archive.namelist())
        for path in assets:
            assert archive.read(path) == (sources / "src" / path).read_bytes()
