"""旧专项账号集合由插件接手后应保留身份和运行设置。"""

from uuid import UUID

import pytest
from auto_mas_core.host.config import ConfigCollection, config_manager
from auto_mas_core.host.utils import IS_WINDOWS, dpapi_encrypt

from zzzod_adapter.adapter import ZzzOdAdapter
from zzzod_adapter.config import ZzzOdConfig


def test_desktop_session_permission_and_default():
    config = ZzzOdConfig.build()
    assert config.Run.ExecutionSession == "main"
    assert ZzzOdAdapter.decl.desktop_session_reason(config, False) == "admin_required"
    assert ZzzOdAdapter.decl.desktop_session_reason(config, True) is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "credentials",
    [
        None,
        pytest.param(
            ("migration@example.invalid", "synthetic migration password"),
            marks=pytest.mark.skipif(not IS_WINDOWS, reason="仅 Windows 支持 DPAPI"),
        ),
    ],
    ids=["settings", "dpapi"],
)
async def test_activate_legacy_accounts(monkeypatch, credentials):
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
        "Run": {"ExecutionSession": "desktop"},
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
    if credentials is not None:
        login, password = credentials
        cipher = f"DPAPI:{dpapi_encrypt(password)}"
        payload["UserData"]["data"][str(uid)]["Game"] = {
            "Account": login,
            "Password": cipher,
        }
    config = ZzzOdConfig.build(payload=payload)
    await config.activate()
    assert config.info.name == "Old manager"
    assert config.Run.ExecutionSession == "desktop"
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
    if credentials is not None:
        saved = persisted["users"]["data"][str(uid)]["Info"]
        assert saved["Id"].startswith("DPAPI:")
        assert saved["Password"] == cipher
    reloaded = ZzzOdConfig.build(payload=persisted)
    await reloaded.activate()
    assert reloaded.Run.ExecutionSession == "desktop"
    assert reloaded.users[uid].Info.SlotIdx == 1001
    assert reloaded.users[uid].Notify.PushLogMode == "逐条"
    if credentials is not None:
        assert reloaded.users[uid].Info.Id == login
        assert reloaded.users[uid].Info.Password == password
