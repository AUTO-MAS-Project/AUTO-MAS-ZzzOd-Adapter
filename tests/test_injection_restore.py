"""实例收尾还原原生配置，但不能回滚本轮产生的未知进度文件。"""

from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from auto_mas_core.host.config import ConfigCollection
from auto_mas_core.host.models_task import TaskItem, TaskScriptItem, TaskUserItem

from zzzod_adapter.auto_proxy import Publisher, ZzzOdAutoProxyWorker
from zzzod_adapter.config import ZzzOdConfig, ZzzOdUserConfig
from zzzod_adapter.expander import ZzzOdExpander
from zzzod_adapter.tools import zzz_od_config as records


@pytest.mark.asyncio
@pytest.mark.parametrize("fault", ["none", "read", "list", "write"])
async def test_restoring_injection_preserves_new_progress_and_reports_partial_failure(
    tmp_path, monkeypatch, fault
):
    monkeypatch.setattr(Publisher, "send", AsyncMock())
    scripts = ConfigCollection.build([ZzzOdConfig])
    await scripts.activate()
    sid = scripts.add(ZzzOdConfig)
    await scripts.commit()
    config = scripts[sid]
    uid = config.users.add(
        ZzzOdUserConfig, payload={"Info": {"Name": "User", "Base": "independent"}}
    )
    await config.users.commit()
    task = TaskItem()
    await task.activate()
    run_script_id = task.scripts.add(
        TaskScriptItem, payload={"info": {"script_id": str(sid)}}
    )
    await task.scripts.commit()
    script = task.scripts[run_script_id]
    run_id = script.users.add(TaskUserItem, payload={"info": {"user_id": str(uid)}})
    await script.users.commit()
    await script.set_current_index(0)
    user = script.users[run_id]
    await user.set_state(status="完成")
    proxy = ZzzOdAutoProxyWorker(ZzzOdExpander(script, config), user, config.users[uid])

    root = tmp_path / "zzz"
    catalog = root / "src/zzz_od/application/mail"
    catalog.mkdir(parents=True)
    (catalog / "mail_const.py").write_text(
        'APP_ID = "mail"\nAPP_NAME = "邮件"\nDEFAULT_GROUP = True\n', encoding="utf-8"
    )
    slot = root / "config/1001"
    record_dir = slot / "app_run_record"
    record_dir.mkdir(parents=True)
    account = slot / "game_account.yml"
    account.write_bytes(b"account: original\n")
    progress = record_dir / "a-opaque.yml"
    progress.write_bytes(b"opaque_progress: original\n")
    backup = tmp_path / "backup"
    records.backup_instance(root, 1001, backup)
    account.write_bytes(b"account: injected\n")
    progress.write_bytes(b"opaque_progress: new\n")
    healthy = record_dir / "z-another.yml"
    healthy.write_bytes(b"opaque_progress: independent\n")
    proxy.script_root_path = root
    proxy._injected_slots = [(1001, backup)]
    proxy._slot_users = {1001: (user, config.users[uid])}
    proxy._shutdown_after_success = True

    read_bytes = Path.read_bytes
    iterdir = Path.iterdir
    atomic_write = records._utils_io.atomic_write

    def read(path):
        if path == progress and fault == "read":
            raise PermissionError("progress is held")
        return read_bytes(path)

    def list_files(path):
        if path == record_dir and fault == "list":
            raise PermissionError("record directory is held")
        return iterdir(path)

    def write(path, payload):
        if path == progress and fault == "write":
            raise PermissionError("progress is held")
        return atomic_write(path, payload)

    with monkeypatch.context() as filesystem:
        filesystem.setattr(Path, "read_bytes", read)
        filesystem.setattr(Path, "iterdir", list_files)
        filesystem.setattr(records._utils_io, "atomic_write", write)
        await proxy._restore_injection()

    assert account.read_bytes() == b"account: original\n"
    if fault != "list":
        assert healthy.read_bytes() == b"opaque_progress: independent\n"
    if fault == "none":
        assert progress.read_bytes() == b"opaque_progress: new\n"
        assert user.status == "完成" and proxy._shutdown_after_success
    else:
        assert user.status == "异常" and not proxy._shutdown_after_success
        assert (backup / "app_run_record/a-opaque.yml").read_bytes() == (
            b"opaque_progress: original\n"
        )
    await proxy._restore_injection()
    if fault != "list":
        assert healthy.read_bytes() == b"opaque_progress: independent\n"
