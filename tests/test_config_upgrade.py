"""旧专项账号集合由插件接手后应保留身份和运行设置。"""

from uuid import UUID

import pytest
from auto_mas_core.host.config import ConfigCollection, config_manager

from zzzod_adapter.config import ZzzOdConfig


@pytest.mark.asyncio
async def test_activate_legacy_accounts(monkeypatch):
    for name in ("games", "PlanConfig"):
        try:
            config_manager.get_collection(name)
        except LookupError:
            monkeypatch.setitem(
                config_manager._collections, name, ConfigCollection.build()
            )

    uid = UUID("1babee9d-5a64-4d33-b9a3-702bf5fb7ced")
    payload = {
        "Info": {"Name": "Old manager"},
        "UserData": {
            "order": [{"uid": str(uid), "type": "ZzzOdUserConfig"}],
            "data": {
                str(uid): {
                    "Info": {
                        "Name": "Old account",
                        "Mode": "native",
                        "Status": False,
                        "SlotIdx": 1001,
                    },
                    "Data": {"ProxyTimes": 7, "LauncherLastGood": "集成"},
                    "Notify": {"PushLogMode": "逐条"},
                }
            },
        },
    }
    config = ZzzOdConfig.build(payload=payload)
    await config.activate()
    assert config.info.name == "Old manager"
    assert [entry.uid for entry in config.users.values()] == [uid]
    user = config.users[uid]
    assert user.info.name == "Old account"
    assert not user.info.enabled
    assert user.Info.Base == "native"
    assert not user.Info.IfQuickConfig
    assert user.Info.SlotIdx == 1001
    assert user.Data.ProxyTimes == 7
    assert user.Data.LauncherLastGood == "集成"
    assert user.Notify.PushLogMode == "逐条"
    assert "UserData" in payload

    persisted = await config.to_dict()
    assert "UserData" not in persisted
    reloaded = ZzzOdConfig.build(payload=persisted)
    await reloaded.activate()
    assert reloaded.users[uid].Info.SlotIdx == 1001
    assert reloaded.users[uid].Notify.PushLogMode == "逐条"
