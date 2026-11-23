"""按一条龙的实例运行方式在已锁托管内展开账号。"""

import asyncio
from datetime import datetime

from auto_mas_core import TaskMode, UserExpander
from auto_mas_core.host.core import Notify
from auto_mas_core.host.models_notification_report import TaskResultReport
from auto_mas_core.host.models_task import TaskUserItem
from auto_mas_core.host.utils import get_logger

from .auto_proxy import ZzzOdAutoProxyWorker
from .config import ZzzOdConfig, ZzzOdUserConfig
from .gui_session import ZzzOdConfigWorker, ZzzOdViewWorker

logger = get_logger("ZZZ-OD 调度器")


class ZzzOdExpander(UserExpander[ZzzOdConfig]):
    """单账号由宿主逐个派发，注入多实例由一轮 worker 共同执行。"""

    async def prepare(self) -> None:
        self._started_at = datetime.now()

    async def finish(self) -> None:
        if self.task_info.mode != TaskMode.AUTO_PROXY:
            return
        users = tuple(self.script_info.users.values())
        now = datetime.now()
        name = self.script_info.info.name
        result = self.script_info.info.result
        try:
            # LogFlow #2072：所有账号会话结束后，此处用托管的 LogFlowTaskReport
            # 提交同一份汇总，保留 Notify 对过滤及去重的所有权。
            await Notify.push_proxy_result(
                title=f"{now:%m-%d} | {name}的自动代理任务报告",
                report=TaskResultReport.from_message(
                    {
                        "title": "自动代理任务报告",
                        "script_name": name,
                        "start_time": f"{self._started_at:%Y-%m-%d %H:%M:%S}",
                        "end_time": f"{now:%Y-%m-%d %H:%M:%S}",
                        "completed_count": sum(user.status == "完成" for user in users),
                        "uncompleted_count": sum(
                            user.status in ("异常", "等待") for user in users
                        ),
                        "result": result,
                    }
                ),
                task_info=self.task_info,
            )
        except Exception as error:
            logger.opt(exception=True).warning(f"推送代理结果失败：{error}")

    def can_run_user(self, entry):
        return super().can_run_user(entry) and (
            self.task_info.mode != TaskMode.AUTO_PROXY or entry.Info.RemainedDay != 0
        )

    def build_worker(self, user, config):
        match self.task_info.mode:
            case TaskMode.SCRIPT_CONFIG:
                return ZzzOdConfigWorker(self, user, config)
            case TaskMode.SCRIPT_VIEW:
                return ZzzOdViewWorker(self, user, config)
            case TaskMode.AUTO_PROXY:
                return ZzzOdAutoProxyWorker(self, user, config)
            case _:
                raise ValueError("一条龙不支持当前执行模式")

    async def dispatch_users(self, users: tuple[TaskUserItem, ...]) -> None:
        if (
            self.task_info.mode != TaskMode.AUTO_PROXY
            or self.script_config.Game.AccountSwitch != "多实例切换"
        ):
            await super().dispatch_users(users)
            return

        inject = []
        direct = []
        for user in users:
            entry = self.resolve_user(user)
            if isinstance(entry, ZzzOdUserConfig) and entry.Info.Base != "native":
                inject.append(user)
            else:
                direct.append(user)

        if inject:
            await self._run_group(tuple(inject))
        await super().dispatch_users(tuple(direct))

    def _binding(self, entry: ZzzOdUserConfig):
        return entry.game if entry.game.game_id != "-" else self.script_config.game

    async def _run_group(self, users: tuple[TaskUserItem, ...]) -> None:
        async with self.lock_user_group(users) as locked:
            if not locked:
                return
            lead, config = locked[0]
            lead_binding = self._binding(config)
            participants = []
            for user, entry in locked:
                binding = self._binding(entry)
                reason = binding.unavailable_reason
                if (binding.game_id, binding.device_id) != (
                    lead_binding.game_id,
                    lead_binding.device_id,
                ):
                    reason = "多实例切换的账号必须绑定同一个游戏和设备"
                if reason:
                    await self.record_user_state(user, status="异常", reason=reason)
                else:
                    participants.append((user, entry))
            if not participants:
                return

            lead, config = participants[0]
            self.script_info.current.index = lead.uid
            await self.script_info.commit()
            runs = tuple(user for user, _ in participants)
            try:
                if self.game_session is not None:
                    await self.game_session.select(config)
                await self.spawn(
                    ZzzOdAutoProxyWorker(self, lead, config, participants=runs)
                )
            except asyncio.CancelledError:
                for user in runs:
                    if user.status in ("等待", "运行"):
                        await user.set_state(status="已取消")
                raise
            except Exception as error:
                for user in runs:
                    if user.status in ("等待", "运行"):
                        await self.record_user_state(
                            user, status="异常", reason=str(error)
                        )
            finally:
                if self.game_session is not None:
                    await self.game_session.release_account()

            for user in runs:
                if user.status in ("等待", "运行"):
                    await self.record_user_state(
                        user, status="异常", reason="一条龙成组运行未返回账号结果"
                    )
