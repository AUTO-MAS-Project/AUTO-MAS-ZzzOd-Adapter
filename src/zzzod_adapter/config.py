#   AUTO-MAS: A Multi-Script, Multi-Config Management and Automation Software
#   Copyright © 2025-2026 AUTO-MAS Team
#
#   This file is part of AUTO-MAS.
#
#   AUTO-MAS is free software: you can redistribute it and/or modify
#   it under the terms of the GNU Affero General Public License
#   as published by the Free Software Foundation, either version 3 of
#   the License, or (at your option) any later version.
#
#   AUTO-MAS is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#   GNU Affero General Public License for more details.
#
#   You should have received a copy of the GNU Affero General Public License
#   along with AUTO-MAS. If not, see <https://www.gnu.org/licenses/>.

"""绝区零一条龙托管和账号配置，沿用原有专项字段。"""

import json
from copy import deepcopy
from typing import Annotated, Any, Literal

from auto_mas_core import ScriptEntry, UserEntry
from auto_mas_core.host.config import (
    ConfigCollection,
    ConfigGroup,
    UiVisibility,
    Virtual,
    collection,
    encrypted,
    legacy,
    ui,
    virtual_field,
)
from auto_mas_core.host.config_types import CliArgumentString, FilePath, FolderPath
from auto_mas_core.host.models_config_queue import Webhook
from auto_mas_core.host.models_config_shared import (
    AccountNameFields,
    AccountRunFields,
    AccountRunStatusFields,
    AccountScriptHookFields,
    _tag_last_status,
    none_as,
)
from auto_mas_core.host.utils import constants as _utils_constants
from pydantic import Field


class ZzzOdUserConfig(UserEntry):
    """绝区零一条龙账号配置（zzz-od 线，MaaEnd 式字段化账号配置）

    账号配置的事实源是本类的 配置字段（web 界面直接编辑，走通用
    updateUser 链路）：Game 区为账号/区服/游戏路径，OneDragon 区为一条龙
    任务编排（JSON，顺序即执行顺序）。运行时由这些字段生成 game_account.yml
    与 one_dragon/_group.yml 注入当前活跃实例槽、结束恢复原状（MAS 不留
    痕迹）。原生（native）来源不使用字段配置，直接以 zzz-od 原生配置运行。
    """

    class DataFields(AccountRunFields, AccountRunStatusFields):
        LauncherLastGood: Annotated[
            Literal["", "原始", "集成"],
            ui(visibility=UiVisibility.HIDE),
        ] = Field(
            default_factory=lambda: "",
            description='智能启动器模式最近一次成功运行的启动器（""=尚未记录；下次智能优先用它）',
        )

    Data: DataFields = Field(default_factory=DataFields)

    class GameFields(ConfigGroup):
        BilibiliAccountName: str = Field(
            default_factory=lambda: "", description="B服登录账号名"
        )

        CustomWinTitle: str = Field(
            default_factory=lambda: "", description="自定义窗口标题"
        )

        Dx12: bool = Field(
            default_factory=lambda: False,
            description="DX12 启动（MAS 便捷开关：注入时把 -use-d3d12 合并进一条龙的 launch_argument_advance；上游无独立字段，勾选框是唯一权威）",
        )

        FullScreen: Literal["0", "1"] = Field(
            default_factory=lambda: "0",
            description="全屏模式（上游枚举原值为字符串：'0'=窗口化 '1'=全屏）",
        )

        GameLanguage: Literal["cn", "en"] = Field(
            default_factory=lambda: "cn", description="游戏界面语言"
        )

        GamePath: FilePath = Field(
            default_factory=lambda: None,
            description="游戏 exe 完整路径（ZenlessZoneZero.exe）",
        )

        GameRegion: Literal["cn", "cn_b", "us", "eu", "asia", "twhkmo"] = Field(
            default_factory=lambda: "cn",
            description="游戏区服（zzz-od game_account.yml 的 game_region 取值）",
        )

        LaunchArgument: bool = Field(
            default_factory=lambda: False,
            description="一条龙游戏启动参数（game.yml 六字段，照抄上游 BasicGameConfig 默认值与取值；一条龙启动游戏时消费，总开关关闭则全部不生效）： 启动参数总开关",
        )

        LaunchArgumentAdvance: str = Field(
            default_factory=lambda: "",
            description="高级参数（原样透传给一条龙拼接，上游不解析，不做 shlex 校验）",
        )

        Monitor: Literal["1", "2", "3", "4"] = Field(
            default_factory=lambda: "1",
            description="显示器序号（上游枚举原值为字符串）",
        )

        Platform: Literal["PC"] = Field(
            default_factory=lambda: "PC",
            description="游戏平台（上游枚举 GamePlatformEnum.PC 的真实值为大写 'PC'）",
        )

        PopupWindow: bool = Field(
            default_factory=lambda: False,
            description="无边框窗口（一条龙拼参时转 -popupwindow）",
        )

        ScreenSize: Literal["1920x1080", "2560x1440", "3840x2160"] = Field(
            default_factory=lambda: "1920x1080", description="窗口尺寸（上游枚举原值）"
        )

        UseCustomWinTitle: bool = Field(
            default_factory=lambda: False, description="是否使用自定义窗口标题"
        )

    Game: GameFields = Field(default_factory=GameFields)

    class InfoFields(AccountNameFields, AccountScriptHookFields):
        Id: Annotated[str, legacy(group="Game", name="Account"), encrypted()] = Field(
            default_factory=lambda: "",
            description="登录账号（手机号/邮箱；留空沿用 zzz-od 已保存的登录态）",
        )

        Password: Annotated[str, legacy(group="Game", name="Password"), encrypted()] = (
            Field(
                default_factory=lambda: "",
                description="登录密码（DPAPI 加密落盘，注入/回读写 game_account.yml 时经 get/set 自动加解密）",
            )
        )

        Base: Annotated[
            Literal["shared", "independent", "native"],
            legacy(
                group="Info",
                name="Mode",
                convert=_utils_constants.normalize_base_source,
            ),
        ] = Field(
            default_factory=lambda: "independent",
            description="base 来源（shared=共享/independent=独立/native=原生）",
        )

        IfQuickConfig: bool = Field(
            default_factory=lambda: True,
            description="是否启用覆写常规配置（已封锁，仅保留字段兼容存量数据：原生来源在 load/update 归一为关，共享/独立来源不消费本开关）",
        )

        LauncherMode: Literal["自动", "原始", "集成"] = Field(
            default_factory=lambda: "自动",
            description="一条龙启动器选择（原生/独立两态通用）： 自动 = 优先用「上次成功」的启动器，启动失败自动换另一个重试并记住下一次 成功的那个；原始/集成 = 固定用对应启动器（对应 exe 未安装时回退可用项）",
        )

        SlotIdx: Annotated[int, Field(ge=-1, le=9999)] = Field(
            default_factory=lambda: -1,
            description="绑定的 zzz-od 实例槽下标（运行/配置会话内临时合成视图写回原生配置，非持久注册）：-1=未分配，首次运行或 「在一条龙内配置」时自动分配空闲 idx 并锁定该槽至会话结束， 此后配置会话与运行时注入都固定使用该槽。新槽从 MAS_SLOT_BASE（1001）起， 退到一条龙「升序找最小空号」够不到的高位段（上限 9999 与之一致放宽）",
        )

    Info: InfoFields = Field(default_factory=InfoFields)

    class NotifyFields(ConfigGroup):
        Enabled: bool = Field(
            default_factory=lambda: False, description="是否启用账号通知"
        )

        IfSendMail: bool = Field(
            default_factory=lambda: False, description="是否发送邮件"
        )

        IfSendStatistic: bool = Field(
            default_factory=lambda: False, description="是否发送账号统计信息"
        )

        IfServerChan: bool = Field(
            default_factory=lambda: False, description="是否启用 Server 酱"
        )

        PushLogMode: Literal["关闭", "逐条", "汇总"] = Field(
            default_factory=lambda: "汇总",
            description="任务报告节点详情的推送模式（运行记录 diff 出的各任务结果）： 关闭 = 不采集；逐条 = 逐条带回时间戳；汇总 = 按状态聚合",
        )

        ServerChanKey: str = Field(
            default_factory=lambda: "", description="Server 酱密钥"
        )

        ToAddress: str = Field(
            default_factory=lambda: "", description="账号通知收件地址"
        )

    Notify: NotifyFields = Field(default_factory=NotifyFields)

    class OneDragonFields(ConfigGroup):
        AfterDone: Literal["无", "关闭游戏", "关机"] = Field(
            default_factory=lambda: "关闭游戏",
            description="游戏结束后操作（仅 MAS 拉起的一条龙运行消费：CLI 传参 --close-game / --shutdown 60；无=不传参，游戏保持运行。 与一条龙原生 GUI 的「结束后」下拉无关——原生 after_done 只在 从 GUI 内启动运行时被消费，CLI 路径不读它）",
        )

        AppList: str = Field(
            default_factory=lambda: "[]",
            description='一条龙任务编排（JSON 数组字符串 [{"app_id": "...", "enabled": true}, ...]， 数组顺序即执行顺序；enabled=false 的任务由 zzz-od 跳过）',
        )

    OneDragon: OneDragonFields = Field(default_factory=OneDragonFields)
    Notify_CustomWebhooks: ConfigCollection[Webhook] = collection(Webhook)

    def getTags(self) -> str:
        tags = []
        last_status = self.Data.LastProxyStatus
        tags.append(
            {
                "text": f"上次：{_tag_last_status(last_status)}",
                "color": "red" if last_status == "失败" else "green",
            }
        )
        base = str(self.Info.Base or "independent")
        if base == "independent":
            try:
                app_list = json.loads(self.OneDragon.AppList or "[]")
            except (TypeError, ValueError):
                app_list = []
            if not isinstance(app_list, list):
                app_list = []
            enabled_count = sum(
                (
                    1
                    for item in app_list
                    if isinstance(item, dict) and item.get("enabled")
                )
            )
            if enabled_count > 0:
                tags.append({"text": f"一条龙：{enabled_count} 项", "color": "orange"})
            else:
                tags.append({"text": "一条龙：未编排", "color": "orange"})
        remained_day = self.Info.RemainedDay
        if remained_day == -1:
            tag_color = "gold"
        elif remained_day == 0:
            tag_color = "red"
        elif remained_day <= 3:
            tag_color = "orange"
        elif remained_day <= 7:
            tag_color = "yellow"
        elif remained_day <= 30:
            tag_color = "blue"
        else:
            tag_color = "green"
        tags.append(
            {
                "text": f"剩余天数：{remained_day}天"
                if remained_day >= 0
                else "剩余天数：无期限",
                "color": tag_color,
            }
        )
        notes = self.Info.Notes
        tags.append(
            {
                "text": f"备注：{notes}"
                if len(notes) <= 20
                else f"备注：{notes[:20]}...",
                "color": "pink",
            }
        )
        return json.dumps(tags, ensure_ascii=False)

    @classmethod
    def normalize_payload(cls, data):
        normalized_data = deepcopy(data) if isinstance(data, dict) else {}
        info = normalized_data.get("Info")
        if (
            isinstance(info, dict)
            and _utils_constants.normalize_base_source(
                info.get("Base", info.get("Mode"))
            )
            == "native"
        ):
            info["IfQuickConfig"] = False
        return normalized_data

    @virtual_field("Info.Tag")
    def compute_Info_Tag(self):
        try:
            return self.getTags()
        except Exception as exc:
            return str(exc)

    class Metadata(UserEntry.Info):
        name: Virtual[str] = None  # pyright: ignore[reportIncompatibleVariableOverride]
        enabled: Virtual[bool] = None  # pyright: ignore[reportIncompatibleVariableOverride]
        proxy_status: Virtual[str] = None  # pyright: ignore[reportIncompatibleVariableOverride]

    info: Metadata = Field(default_factory=Metadata)  # pyright: ignore[reportIncompatibleVariableOverride]

    @virtual_field("info.name")
    def plugin_name(self) -> str:
        return self.Info.Name

    @virtual_field("info.enabled")
    def plugin_enabled(self) -> bool:
        return self.Info.Status

    @virtual_field("info.proxy_status")
    def plugin_proxy_status(self) -> str:
        return self.Data.LastProxyStatus

    async def _activate_from_payload(
        self, payload: dict[str, Any], *, regenerate_uuids: bool = False
    ) -> None:
        await super()._activate_from_payload(
            self.normalize_payload(payload), regenerate_uuids=regenerate_uuids
        )


class ZzzOdConfig(ScriptEntry):
    "绝区零一条龙配置（zzz-od 线）"

    class GameFields(ConfigGroup):
        AccountSwitch: Literal["单实例切换", "多实例切换", "MAS切换"] = Field(
            default_factory=lambda: "单实例切换",
            description="多账号账号切换方式（托管级下拉，value 对应 manager 的分派分支）： 单实例切换（默认，推荐）= 逐账号独立会话：注入该账号配置 → 单实例 运行（仅运行当前，无槽间切换）→ 跑完关闭 → 下一个账号。失败域 隔离最好，重试只重启失败账号； 多实例切换（不推荐）= 全部启用账号合并为一轮多账号运行，一条龙内部 依次切换账号。总时长最短，但单槽失败会拖整轮重试、切换次数随 账号数线性增长； MAS切换 = MAS 侧 OCR 操控游戏完成账号切换后交一条龙运行（暂未开放）。",
        )

        Arguments: CliArgumentString = Field(
            default_factory=lambda: "", description="游戏启动参数"
        )

        CloseOnFinish: bool = Field(
            default_factory=lambda: True,
            description="任务结束后由 MAS 关闭游戏（收尾/手动停止时按进程名结束游戏本体， 覆盖失败重试与手动停止场景，是「结束后操作」的兜底）。与账号级 OneDragon.AfterDone 下发的 --close-game 相互独立，同时配置会各 执行一次（无害）",
        )

        Enabled: bool = Field(
            default_factory=lambda: False,
            description="是否由 MAS 管理游戏进程（任务前启动游戏由此开关总控）",
        )

        LaunchBeforeTask: bool = Field(
            default_factory=lambda: False,
            description="任务前由 MAS 启动游戏（检测到游戏进程正在运行时跳过重复启动）",
        )

        Path: FilePath = Field(
            default_factory=lambda: None,
            description="游戏路径（游戏本体 ZenlessZoneZero.exe）",
        )

        WaitTime: Annotated[int, Field(ge=0, le=9999), none_as(0)] = Field(
            default_factory=lambda: 60,
            description="启动游戏后的等待时间（秒）",
        )

    Game: GameFields = Field(default_factory=GameFields)

    class InfoFields(ConfigGroup):
        Name: str = Field(
            default_factory=lambda: "新绝区零一条龙托管", description="托管名称"
        )

        RootPath: FolderPath = Field(
            default_factory=lambda: None,
            description="zzz-od 安装根目录（含 OneDragon 启动器、src 与 config）",
        )

    Info: InfoFields = Field(default_factory=InfoFields)

    class RunFields(ConfigGroup):
        HardTimeLimit: Annotated[int, Field(ge=1, le=9999), none_as(1)] = Field(
            default_factory=lambda: 120,
            description="单账号运行总时限（分钟），包含等待和全部重试",
        )

        ProxyTimesLimit: Annotated[int, Field(ge=0, le=9999), none_as(0)] = Field(
            default_factory=lambda: 0, description="每日代理次数上限"
        )

        RunTimeLimit: Annotated[int, Field(ge=1, le=9999), none_as(1)] = Field(
            default_factory=lambda: 40,
            description="单次运行超时时间（分钟）；这是日志停滞超时（latest_time 距今），不是 总时长上限——一条龙持续写日志就不会触发；启动器层故障（不写应用层 日志）也靠它兜底超时后切换启动器",
        )

        RunTimesLimit: Annotated[int, Field(ge=1, le=9999), none_as(1)] = Field(
            default_factory=lambda: 3, description="单次任务重试次数"
        )

    Run: RunFields = Field(default_factory=RunFields)
    users: ConfigCollection[ZzzOdUserConfig] = collection(ZzzOdUserConfig)

    class Metadata(ScriptEntry.Info):
        name: Virtual[str] = None  # pyright: ignore[reportIncompatibleVariableOverride]

    info: Metadata = Field(default_factory=Metadata)  # pyright: ignore[reportIncompatibleVariableOverride]

    @virtual_field("info.name")
    def plugin_name(self) -> str:
        return self.Info.Name

    async def _activate_from_payload(
        self, payload: dict[str, Any], *, regenerate_uuids: bool = False
    ) -> None:
        """在集合激活前将旧账号集合交给插件宿主约定的 users 字段。"""
        normalized = deepcopy(payload)
        if "UserData" in normalized:
            normalized.setdefault("users", normalized.pop("UserData"))
        await super()._activate_from_payload(
            normalized, regenerate_uuids=regenerate_uuids
        )
