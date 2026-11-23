"""覆盖配置会话取消后的文件恢复和只看模式隔离。"""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from auto_mas_core import TaskMode, UserExpander
from auto_mas_core.host.config import ConfigCollection
from auto_mas_core.host.models_task import TaskItem, TaskScriptItem, TaskUserItem

from zzzod_adapter import gui_session
from zzzod_adapter.config import ZzzOdConfig, ZzzOdUserConfig
from zzzod_adapter.tools import (
    find_active_instance,
    instance_dir,
    read_app_group,
    write_app_group,
)


@pytest.mark.parametrize(
    ("worker_class", "mode", "native"),
    [
        (gui_session.ZzzOdConfigWorker, TaskMode.SCRIPT_CONFIG, False),
        (gui_session.ZzzOdConfigWorker, TaskMode.SCRIPT_CONFIG, True),
        (gui_session.ZzzOdViewWorker, TaskMode.SCRIPT_VIEW, False),
    ],
)
async def test_gui_session_restores_registry_and_view_skips_readback(
    tmp_path, monkeypatch, worker_class, mode, native
):
    work_dir = tmp_path / "mas"
    work_dir.mkdir()
    monkeypatch.chdir(work_dir)
    root = tmp_path / "onedragon"
    (root / "src").mkdir(parents=True)
    launcher = root / "OneDragon-RuntimeLauncher.exe"
    launcher.touch()
    slot_dir = instance_dir(root, 1001)
    slot_dir.mkdir(parents=True)
    registry = root / "config" / "one_dragon.yml"
    baseline = b"instance_list:\n  - idx: 1\n    name: Native\n    active: true\n"
    registry.write_bytes(baseline.replace(b"true", b"false") if native else baseline)
    old_apps = [{"app_id": "mail", "enabled": False}]
    slot_apps = [{"app_id": "history", "enabled": True}]
    new_apps = [{"app_id": "coffee", "enabled": True}]
    write_app_group(slot_dir, slot_apps)
    scripts = ConfigCollection.build([ZzzOdConfig])
    await scripts.activate()
    sid = scripts.add(ZzzOdConfig, payload={"Info": {"RootPath": str(root)}})
    await scripts.commit()
    script = scripts[sid]
    uid = script.users.add(
        ZzzOdUserConfig,
        payload={
            "Info": {"SlotIdx": 1001},
            "OneDragon": {"AppList": json.dumps(old_apps)},
        },
    )
    await script.users.commit()
    user_config = script.users[uid]
    monkeypatch.setattr(gui_session, "Config", SimpleNamespace(ScriptConfig=scripts))

    task = TaskItem.build(payload={"info": {"mode": mode}})
    await task.activate()
    params = {"instance_idx": 1} if native else {}
    rid = task.scripts.add(
        TaskScriptItem, payload={"info": {"script_id": str(sid), "params": params}}
    )
    await task.scripts.commit()
    run = task.scripts[rid]
    target = "default" if native else str(uid)
    user_run_id = run.users.add(TaskUserItem, payload={"info": {"user_id": target}})
    await run.users.commit()
    user_run = run.users[user_run_id]

    class Expander(UserExpander):
        def build_worker(self, user, config):
            return worker_class(self, user, config)

    expander = Expander(run, script)
    shown = []
    started = asyncio.Event()
    kill = AsyncMock()

    async def open_process(path, **_kwargs):
        assert path == launcher
        assert find_active_instance(root)["idx"] == (1 if native else 1001)
        if not native:
            shown.extend(read_app_group(slot_dir))
            write_app_group(slot_dir, new_apps)
        started.set()

    monkeypatch.setattr(
        gui_session,
        "ProcessManager",
        lambda: SimpleNamespace(open_process=open_process, kill=kill),
    )
    expander.start()
    try:
        await asyncio.wait_for(started.wait(), timeout=2)
    finally:
        await expander.stop()

    assert expander.error is None
    kill.assert_awaited_once()
    assert user_run.status == "已取消"
    if native:
        assert find_active_instance(root) is None
        assert json.loads(user_config.OneDragon.AppList) == old_apps
        return

    assert registry.read_bytes() == baseline
    if mode == TaskMode.SCRIPT_VIEW:
        assert shown == slot_apps
        assert json.loads(user_config.OneDragon.AppList) == old_apps
    else:
        assert shown == old_apps
        assert json.loads(user_config.OneDragon.AppList) == new_apps
