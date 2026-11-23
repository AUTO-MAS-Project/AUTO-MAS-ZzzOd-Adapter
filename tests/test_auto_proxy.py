"""单账号代理通过宿主 worker 启动、采集原始日志并还原配置。"""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from auto_mas_core import UserExpander
from auto_mas_core.host.config import ConfigCollection
from auto_mas_core.host.models_task import TaskItem, TaskScriptItem, TaskUserItem

from zzzod_adapter import auto_proxy
from zzzod_adapter.config import ZzzOdConfig, ZzzOdUserConfig
from zzzod_adapter.tools import instance_dir, write_app_group


@pytest.mark.parametrize("cancel", [False, True])
async def test_single_account_worker_persists_result_or_restores_on_cancel(
    tmp_path, monkeypatch, cancel
):
    work_dir = tmp_path / "mas"
    work_dir.mkdir()
    monkeypatch.chdir(work_dir)
    root = tmp_path / "onedragon"
    catalog = root / "src" / "zzz_od" / "application"
    catalog.mkdir(parents=True)
    (catalog / "mail_const.py").write_text('APP_ID = "mail"\nAPP_NAME = "Mail"\n')
    launcher = root / "OneDragon-RuntimeLauncher.exe"
    launcher.touch()
    slot = instance_dir(root, 1001)
    slot.mkdir(parents=True)
    write_app_group(slot, [{"app_id": "previous", "enabled": True}])
    registry = root / "config" / "one_dragon.yml"
    original = b"instance_list:\n  - idx: 1\n    name: Native\n    active: true\n"
    registry.write_bytes(original)
    scripts = ConfigCollection.build([ZzzOdConfig])
    await scripts.activate()
    sid = scripts.add(
        ZzzOdConfig,
        payload={
            "Info": {"RootPath": str(root)},
            "Game": {"CloseOnFinish": False},
            "Run": {"RunTimesLimit": 1},
        },
    )
    await scripts.commit()
    script = scripts[sid]
    uid = script.users.add(
        ZzzOdUserConfig,
        payload={
            "Info": {"SlotIdx": 1001, "RemainedDay": 3},
            "OneDragon": {
                "AppList": json.dumps([{"app_id": "mail", "enabled": True}]),
                "AfterDone": "无",
            },
        },
    )
    await script.users.commit()
    account = script.users[uid]
    task = TaskItem()
    await task.activate()
    rid = task.scripts.add(TaskScriptItem, payload={"info": {"script_id": str(sid)}})
    await task.scripts.commit()
    run = task.scripts[rid]
    urid = run.users.add(TaskUserItem, payload={"info": {"user_id": str(uid)}})
    await run.users.commit()
    user = run.users[urid]

    class Expander(UserExpander):
        def build_worker(self, user, config):
            return auto_proxy.ZzzOdAutoProxyWorker(self, user, config)

    expander = Expander(run, script)
    expander.history = SimpleNamespace(
        begin_user_history_capture=Mock(), save_user_history=AsyncMock()
    )
    ready = asyncio.Event()
    running = True

    async def launch(path, *_args, **_kwargs):
        assert path == launcher
        assert registry.read_bytes() != original

    async def monitor(_path, started_at):
        nonlocal running
        if not cancel:
            records = slot / "app_run_record"
            records.mkdir(exist_ok=True)
            (records / "mail.yml").write_text("run_status: 1\n")
            running = False
            await log_callback(["completed\n"], started_at)
        ready.set()

    def monitor_factory(_time_range, _time_format, callback):
        nonlocal log_callback
        log_callback = callback
        return SimpleNamespace(start_monitor_file=monitor, stop=AsyncMock())

    async def is_running():
        return running

    async def kill():
        assert registry.read_bytes() != original

    log_callback = None
    monkeypatch.setattr(auto_proxy, "Config", SimpleNamespace(ScriptConfig=scripts))
    monkeypatch.setattr(auto_proxy, "LogMonitor", monitor_factory)
    monkeypatch.setattr(
        auto_proxy,
        "ProcessManager",
        lambda **_kwargs: SimpleNamespace(
            open_process=launch, is_running=is_running, kill=kill
        ),
    )
    monkeypatch.setattr(
        auto_proxy, "process", SimpleNamespace(kill_process=AsyncMock())
    )
    monkeypatch.setattr(
        auto_proxy, "Notify", SimpleNamespace(push_statistics_report=AsyncMock())
    )

    expander.start()
    try:
        await asyncio.wait_for(ready.wait(), timeout=5)
        if not cancel:
            await asyncio.wait_for(expander.accomplish.wait(), timeout=5)
    finally:
        await expander.stop()

    assert expander.error is None
    assert registry.read_bytes() == original
    expander.history.save_user_history.assert_awaited_once()
    if cancel:
        assert user.status == "已取消"
        assert account.Data.ProxyTimes == 0
        assert account.Info.RemainedDay == 3
    else:
        assert user.status == "完成"
        assert account.Data.ProxyTimes == 1
        assert account.Info.RemainedDay == 2
        assert account.Data.LauncherLastGood == "集成"
