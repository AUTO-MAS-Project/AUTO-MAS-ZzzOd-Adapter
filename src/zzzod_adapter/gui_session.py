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

"""使用宿主 worker 生命周期运行一条龙原生 GUI 会话。"""

import asyncio
import json
from contextlib import ExitStack

from auto_mas_core import Config, ModeWorker, TaskMode
from auto_mas_core.host.services import script_install
from auto_mas_core.host.utils import ProcessInfo, ProcessManager, get_logger

from .config import ZzzOdUserConfig
from .launchers import find_launcher_exe
from .slots import collect_used_slot_idxs, ensure_user_slot, recycle_unbound_slots
from .tools import (
    archive_mas_config_backup,
    archive_onedragon_backup,
    collect_mas_user_info,
    find_active_instance,
    instance_dir,
    launch_args_patch,
    normalize_app_group_entries,
    read_after_done,
    read_app_group,
    read_game,
    read_game_account,
    restore_instance_view,
    set_active_instance,
    split_dx12_argument,
    user_field_patch,
    write_app_group,
    write_game,
    write_game_account,
    write_instance_view,
)

logger = get_logger("ZZZ-OD 脚本设置")


class _GuiSession(ModeWorker):
    """共享打开和恢复逻辑，专用 worker 声明不同的公开调度模式。"""

    def __init__(self, expander, user, config):
        super().__init__(expander, user, config)
        self.cur_user_config = config
        self.view_only = self.mode == TaskMode.SCRIPT_VIEW
        self._session_slot = None
        self._original_active_idx: int | None = None
        self._session_native_idx: int | None = None
        self._changed_native_active = False
        self._installation = ExitStack()
        self._has_installation = False
        self._launched = False
        self.process_manager = ProcessManager()

    async def check(self) -> str | None:
        if self.cur_user_config is not None and not isinstance(
            self.cur_user_config, ZzzOdUserConfig
        ):
            return "绝区零一条龙账号配置类型错误"
        root = self.expander.script_config.Info.RootPath
        if root is None:
            return "请先配置绝区零一条龙安装目录"
        self.root_path = root.resolve()
        self.exe_path = find_launcher_exe(self.root_path)
        if self.cur_user_config is None:
            idx = self.expander.context.params.get("instance_idx")
            if idx is not None and (type(idx) is not int or idx < 0):
                return "instance_idx 必须为非负整数"
            self._session_native_idx = idx
        return None

    async def prepare(self) -> None:
        self._installation.enter_context(
            script_install.installation_access(self.root_path)
        )
        self._has_installation = True

    async def main_logic(self) -> None:
        # 用户会话：合成注册表视图（仅本槽，active=本槽）+ 以 MAS 字段为基线
        # 注入绑定槽（GUI 所见即本页配置，不清运行记录）；关闭时回读 GUI 改动。
        # 查看会话（view_only）跳过基线注入——槽里是刚恢复的历史备份，所见即备份；
        # 也跳过 MAS 槽归档（恢复动作自身已归档恢复前内容）
        if self.cur_user_config is not None:
            restore_instance_view(self.root_path)  # 闪退自愈
            # 归档点：一条龙原生配置快照——必须在 ensure_user_slot（可能注册
            # 新槽）与合成视图写入之前，捕获未被本次会话触碰的原生状态
            try:
                archive_onedragon_backup(self.root_path)
            except Exception as e:
                logger.opt(exception=True).warning(f"归档 zzz-od 原生配置快照失败: {e}")
            # 孤儿槽回收：与运行注入同口径，回收在 ensure_user_slot 之前——
            # 腾出的号本次会话即可复用（原生配置快照已归档在前，回收仍可找回）。
            # 查看会话（只读预览历史备份）跳过：用户只是看，不该在安装目录里
            # 产生删除副作用（整目录拷贝+删除，线程里跑）
            if not self.view_only:
                await asyncio.to_thread(
                    recycle_unbound_slots,
                    self.root_path,
                    scripts=Config.ScriptConfig,
                    exclude_script_id=self.script_info.script_id,
                )
            used = collect_used_slot_idxs(
                self.root_path,
                scripts=Config.ScriptConfig,
                exclude_uids={self.cur_user_config.uid},
            )
            slot = await ensure_user_slot(
                self.root_path,
                self.cur_user_config,
                used,
                script_id=self.script_info.script_id,
                owner_uid=str(self.cur_user_config.uid),
            )
            self._session_slot = slot
            write_instance_view(
                self.root_path,
                [(slot, f"MAS-{self.cur_user_config.Info.Name}")],
                active_idx=slot,
                after_done=None
                if self.view_only
                else str(self.cur_user_config.OneDragon.AfterDone or "关闭游戏"),
            )
            if self.view_only:
                logger.info(
                    f"启动 zzz-od 原生查看: {self.exe_path} (用户绑定槽 {slot:02d}, "
                    f"只读预览，不注入不回读)"
                )
            else:
                # MAS 账号槽快照（含配队等全部内容），供配置恢复——统一入口
                # 会先物化本页账号+编排进槽（它们只存在 UserData，槽要会话
                # 注入才带上；直接快照会漏掉，恢复会把本页字段清空）
                if instance_dir(self.root_path, slot).is_dir():
                    archive_mas_config_backup(
                        self.script_info.script_id,
                        slot,
                        instance_dir(self.root_path, slot),
                        self.cur_user_config,
                        meta=collect_mas_user_info(self.cur_user_config),
                    )
                cfg = self.cur_user_config
                apps = json.loads(cfg.OneDragon.AppList or "[]")
                if not isinstance(apps, list):
                    raise ValueError("一条龙任务编排数据异常, 请重新编辑任务配置")
                directory = instance_dir(self.root_path, slot)
                write_game_account(directory, user_field_patch(cfg))
                write_game(directory, launch_args_patch(cfg))
                write_app_group(directory, normalize_app_group_entries(apps))
                logger.info(
                    f"启动 zzz-od 原生设置: {self.exe_path} (用户绑定槽 {slot:02d}, "
                    f"以 MAS 配置为基线)"
                )
        else:
            # 托管级会话（直控「在一条龙内配置」入口）：先自愈崩溃残留的
            # 合成视图，保证拉起的是完整原生实例列表，不做隔离与注入。
            # 指定了会话实例时把原生活跃临时切过去（GUI 打开即正在编辑的
            # 实例），原活跃在会话结束还原
            restore_instance_view(self.root_path)
            if self._session_native_idx is not None:
                active = find_active_instance(self.root_path)
                self._original_active_idx = (
                    int(active["idx"]) if active is not None else None
                )
                if self._original_active_idx != self._session_native_idx:
                    set_active_instance(self.root_path, self._session_native_idx)
                    self._changed_native_active = True
            logger.info(f"启动 zzz-od 原生设置: {self.exe_path}")
        # 无参数启动 = GUI 模式；启动器要求管理员权限，elevated 避免二次 UAC
        await self.process_manager.open_process(
            self.exe_path,
            target_process=ProcessInfo(
                name=self.exe_path.name,
                exe=str(self.exe_path),
                cmdline=None,
            ),
            elevated=True,
        )
        self._launched = True
        await asyncio.Future()

    async def _readback_user_fields(self, slot: int) -> None:
        """把 GUI 会话落盘的账号字段、启动参数与任务编排回读到 MAS 账号字段。

        - 区服/路径/语言/B服名：无条件回读（客观字段，槽值即真相）；
        - 账号/密码：槽值非空才回读（留空=沿用登录态语义，避免清空被读回）；
        - 启动参数：无条件回读，-use-d3d12 拆到 Dx12 开关（勾选框为唯一权威）；
        - 任务编排：取 ``_group.yml`` 全量条目顺序（含未启用项）整表进 AppList
          （运行侧 parse_user_apps 只消费启用项，未启用项原位保留顺序）。
        """

        cfg = self.cur_user_config
        if cfg is None:
            return
        slot_dir = instance_dir(self.root_path, slot)
        account = read_game_account(slot_dir)
        account_fields = type(cfg.Game).model_validate(
            {
                "GameRegion": str(account.get("game_region") or "cn"),
                "GamePath": str(account.get("game_path") or ""),
                "GameLanguage": str(account.get("game_language") or "cn"),
                "BilibiliAccountName": str(account.get("bilibili_account_name") or ""),
            }
        )
        cfg.Game.GameRegion = account_fields.GameRegion
        cfg.Game.GamePath = account_fields.GamePath
        cfg.Game.GameLanguage = account_fields.GameLanguage
        cfg.Game.BilibiliAccountName = account_fields.BilibiliAccountName
        await cfg.commit()
        if str(account.get("account") or "").strip():
            cfg.Info.Id = str(account.get("account"))
            await cfg.commit()
        if str(account.get("password") or "").strip():
            cfg.Info.Password = str(account.get("password"))
            await cfg.commit()
        # 启动参数：客观字段无条件回读（GUI 内改了 -use-d3d12 等也要同步回
        # MAS 字段，否则下次注入会被本页旧值覆盖）；缺失键合并上游默认值；
        # -use-d3d12 拆到 Dx12 开关，高级参数只存其余部分（勾选框为唯一权威）
        game_cfg = read_game(slot_dir)
        cfg.Game.LaunchArgument = bool(game_cfg.get("launch_argument", False))
        await cfg.commit()
        launch_fields = type(cfg.Game).model_validate(
            {
                "ScreenSize": str(game_cfg.get("screen_size") or "1920x1080"),
                "FullScreen": str(game_cfg.get("full_screen") or "0"),
                "Monitor": str(game_cfg.get("monitor") or "1"),
            }
        )
        cfg.Game.ScreenSize = launch_fields.ScreenSize
        cfg.Game.FullScreen = launch_fields.FullScreen
        cfg.Game.PopupWindow = bool(game_cfg.get("popup_window", False))
        has_dx12, advance_rest = split_dx12_argument(
            str(game_cfg.get("launch_argument_advance") or "")
        )
        cfg.Game.Dx12 = has_dx12
        cfg.Game.LaunchArgumentAdvance = advance_rest
        cfg.Game.Monitor = launch_fields.Monitor
        await cfg.commit()
        all_apps = normalize_app_group_entries(read_app_group(slot_dir))
        cfg.OneDragon.AppList = json.dumps(all_apps, ensure_ascii=False)
        await cfg.commit()
        # 「结束后」：视图由会话注入该键，GUI 所见即可回读；必须在
        # restore_instance_view 还原前执行（本函数由 final_task 在还原前调用）
        cfg.OneDragon.AfterDone = (
            type(cfg.OneDragon)
            .model_validate({"AfterDone": read_after_done(self.root_path)})
            .AfterDone
        )
        await cfg.commit()
        logger.info(
            f"绑定槽 {slot:02d} 会话改动已回读账号配置 (任务 {len(all_apps)} 项)"
        )

    def _restore_native_active(self) -> None:
        """会话结束还原会话前的原生活跃实例（仅做过临时切换时）。"""

        if self._changed_native_active:
            set_active_instance(self.root_path, self._original_active_idx)
            self._changed_native_active = False

    async def finish(self) -> None:
        if not self._has_installation:
            return
        try:
            try:
                if (
                    self._launched
                    and self._session_slot is not None
                    and not self.view_only
                ):
                    await self._readback_user_fields(self._session_slot)
            finally:
                try:
                    await self.process_manager.kill()
                finally:
                    try:
                        restore_instance_view(self.root_path)
                    finally:
                        self._restore_native_active()
        finally:
            self._installation.close()
            self._has_installation = False


class ZzzOdConfigWorker(_GuiSession):
    """原生 GUI 配置会话。"""

    mode = TaskMode.SCRIPT_CONFIG


class ZzzOdViewWorker(_GuiSession):
    """原生 GUI 查看会话，关闭时跳过写回。"""

    mode = TaskMode.SCRIPT_VIEW
