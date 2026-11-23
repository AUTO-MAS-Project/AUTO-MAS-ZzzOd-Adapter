"""改动一条龙原生实例前应保留原件，防止插件迁移后无法找回配置。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
from auto_mas_core.host.config import ConfigCollection, config_manager
from fastapi import FastAPI

from zzzod_adapter import api
from zzzod_adapter.config import ZzzOdConfig
from zzzod_adapter.tools.backup_archive import (
    get_onedragon_backup_dir,
    list_onedragon_backups,
)


async def test_rename_native_instance_archives_original(tmp_path, monkeypatch):
    work_dir = tmp_path / "mas"
    work_dir.mkdir()
    monkeypatch.chdir(work_dir)
    root = tmp_path / "onedragon"
    (root / "src").mkdir(parents=True)
    (root / "config" / "01").mkdir(parents=True)
    registry = root / "config" / "one_dragon.yml"
    original = b"instance_list:\n  - idx: 1\n    name: Original\n    active: true\n"
    registry.write_bytes(original)
    scripts = ConfigCollection.build([ZzzOdConfig])
    await scripts.activate()
    uid = scripts.add(ZzzOdConfig, payload={"Info": {"RootPath": str(root)}})
    await scripts.commit()
    monkeypatch.setattr(
        api,
        "Config",
        SimpleNamespace(
            ScriptConfig=scripts, flush=config_manager.flush, add_user=AsyncMock()
        ),
    )
    app = FastAPI()
    app.include_router(api.router)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/zzzod/instances/rename",
            json={"scriptId": str(uid), "instanceIdx": 1, "name": "Renamed"},
        )
    result = response.json()
    assert result["status"] == "success", result
    assert result["data"][0]["name"] == "Renamed"
    assert b"Renamed" in registry.read_bytes()
    (stamp,) = list_onedragon_backups(root)
    backup = get_onedragon_backup_dir(root, stamp)
    assert backup is not None
    assert (backup / "one_dragon.yml").read_bytes() == original
