"""单账号和多实例代理共用宿主调度生命周期。"""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
import yaml
from auto_mas_core import GameEntry
from auto_mas_core.host.config import ConfigCollection, config_manager
from auto_mas_core.host.models_task import TaskItem, TaskScriptItem, TaskUserItem

from zzzod_adapter import auto_proxy
from zzzod_adapter.config import ZzzOdConfig, ZzzOdUserConfig
from zzzod_adapter.expander import ZzzOdExpander
from zzzod_adapter.tools import instance_dir, write_app_group


@pytest.mark.parametrize(
    ("grouped", "cancel", "fail_second", "split_targets", "native_second"),
    [
        (False, False, False, False, False),
        (False, True, False, False, False),
        (True, False, False, False, False),
        (True, True, False, False, False),
        (True, False, True, False, False),
        (True, False, True, True, False),
        (True, False, False, True, False),
        (True, False, False, True, "injected-shutdown"),
        (True, False, True, True, "injected-shutdown"),
        (True, False, False, True, "native-shutdown"),
    ],
)
async def test_worker_persists_result_or_restores_on_cancel(
    tmp_path, monkeypatch, grouped, cancel, fail_second, split_targets, native_second
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
    if native_second == "native-shutdown":
        original += "after_done: 关机\n".encode()
    registry.write_bytes(original)
    if split_targets:
        collections = dict(config_manager._collections)
        collections.pop("games", None)
        monkeypatch.setattr(config_manager, "_collections", collections)
        games = ConfigCollection.build([GameEntry], name="games")
        await games.activate()
        game_id = games.add(GameEntry)
        await games.commit()
    scripts = ConfigCollection.build([ZzzOdConfig])
    await scripts.activate()
    sid = scripts.add(
        ZzzOdConfig,
        payload={
            "Info": {"RootPath": str(root)},
            "Game": {
                "CloseOnFinish": False,
                "AccountSwitch": "多实例切换" if grouped else "单实例切换",
            },
            "Run": {"RunTimesLimit": 1},
        },
    )
    await scripts.commit()
    script = scripts[sid]
    task = TaskItem()
    await task.activate()
    rid = task.scripts.add(TaskScriptItem, payload={"info": {"script_id": str(sid)}})
    await task.scripts.commit()
    run = task.scripts[rid]
    accounts = []
    users = []
    slots = [slot]
    if grouped:
        second_slot = instance_dir(root, 1 if native_second else 1002)
        second_slot.mkdir()
        if native_second:
            (second_slot / "game_account.yml").write_text("game_path: game.exe\n")
        slots.append(second_slot)
    for index, directory in enumerate(slots, start=1):
        game = {"game_id": game_id} if split_targets and index == 2 else {}
        uid = script.users.add(
            ZzzOdUserConfig,
            payload={
                "game": game,
                "Info": {
                    "Base": "native" if native_second and index == 2 else "shared",
                    "Name": f"Account{index}",
                    "SlotIdx": int(directory.name),
                    "RemainedDay": 3,
                    "Id": f"fixture-{index}",
                    "Password": "fixture-password",
                },
                "OneDragon": {
                    "AppList": json.dumps([{"app_id": "mail", "enabled": True}]),
                    "AfterDone": "关机"
                    if split_targets
                    and index == 1
                    and native_second != "native-shutdown"
                    else "无",
                },
            },
        )
        await script.users.commit()
        accounts.append(script.users[uid])
        urid = run.users.add(TaskUserItem, payload={"info": {"user_id": str(uid)}})
        await run.users.commit()
        users.append(run.users[urid])

    expander = ZzzOdExpander(run, script)
    expander.history = SimpleNamespace(
        begin_user_history_capture=Mock(), save_user_history=AsyncMock()
    )
    ready = asyncio.Event()
    running = True
    launched_slots = []

    async def launch(path, *args, **_kwargs):
        nonlocal running
        running = True
        assert path == launcher
        if native_second:
            assert accounts[1 if launched_slots else 0].is_locked
        else:
            assert registry.read_bytes() != original
            assert all(account.is_locked for account in accounts)
        shutdown.assert_not_awaited()
        if "--instance" in args:
            launched_slots.append(
                tuple(map(int, args[args.index("--instance") + 1].split(",")))
            )
        else:
            active = yaml.safe_load(registry.read_bytes())["instance_list"]
            launched_slots.append(tuple(row["idx"] for row in active if row["active"]))

    async def monitor(_path, started_at):
        nonlocal running
        if not cancel:
            for i, directory in enumerate(slots):
                if int(directory.name) not in launched_slots[-1]:
                    continue
                records = directory / "app_run_record"
                records.mkdir(exist_ok=True)
                status = 2 if fail_second and i == 1 else 1
                (records / "mail.yml").write_text(f"run_status: {status}\n")
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
        if not native_second:
            assert registry.read_bytes() != original
            assert all(account.is_locked for account in accounts)

    async def schedule_shutdown(*args):
        assert args == ("shutdown", "/s", "/t", "60")
        assert launched_slots == [(1001,), (int(slots[1].name),)]
        assert registry.read_bytes() == original
        assert not any(account.is_locked for account in accounts)
        return SimpleNamespace(wait=AsyncMock(return_value=0))

    shutdown = AsyncMock(side_effect=schedule_shutdown)
    monkeypatch.setattr(auto_proxy, "create_subprocess", shutdown)

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

    report = AsyncMock()
    monkeypatch.setattr("zzzod_adapter.expander.Notify.push_proxy_result", report)

    expander.start()
    try:
        await asyncio.wait_for(ready.wait(), timeout=5)
        if not cancel:
            await asyncio.wait_for(expander.accomplish.wait(), timeout=5)
    finally:
        await expander.stop()

    assert expander.error is None
    report.assert_awaited_once()
    result = report.await_args.kwargs["report"]
    assert result.completed_count == (0 if cancel else len(users) - fail_second)
    assert result.uncompleted_count == int(fail_second)
    assert registry.read_bytes() == original
    assert not any(account.is_locked for account in accounts)
    expected_launches = (
        [(1001,), (int(slots[1].name),)]
        if split_targets
        else [tuple(int(directory.name) for directory in slots)]
    )
    assert launched_slots == expected_launches
    assert shutdown.await_count == int(split_targets and not fail_second)
    assert expander.history.save_user_history.await_count == (
        1 if cancel else len(users)
    )
    for i, (user, account) in enumerate(zip(users, accounts, strict=True)):
        if cancel:
            assert user.status == "已取消"
            assert account.Data.ProxyTimes == 0
            assert account.Info.RemainedDay == 3
        elif fail_second and i == 1:
            assert user.status == "异常"
            assert account.Data.ProxyTimes == 0
            assert account.Info.RemainedDay == 3
        else:
            assert user.status == "完成"
            assert account.Data.ProxyTimes == 1
            assert account.Info.RemainedDay == 2
    if not cancel and not fail_second:
        assert accounts[0].Data.LauncherLastGood == "集成"
