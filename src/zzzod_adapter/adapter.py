"""将插件配置、执行器和专项路由注册到 MAS。"""

from auto_mas_core import ScriptAdapterPlugin, ScriptEntry, ScriptTypeDecl
from auto_mas_core.host.utils import IS_ELEVATED
from fastapi import APIRouter

from .api import router
from .config import ZzzOdConfig, ZzzOdUserConfig
from .expander import ZzzOdExpander

_api = APIRouter(prefix="/api/scripts", tags=["脚本管理"])
_api.include_router(router)


def _supports_desktop_session(_config: ScriptEntry) -> bool:
    return IS_ELEVATED


def _new_user_defaults() -> dict:
    return {"Info": {"Base": "native", "IfQuickConfig": False}}


class ZzzOdAdapter(ScriptAdapterPlugin):
    script_type_key = "ZzzOd"
    api_router = _api
    decl = ScriptTypeDecl(
        script_type=ZzzOdConfig,
        user_type=ZzzOdUserConfig,
        expander_class=ZzzOdExpander,
        activity_game="zenless",
        game_kinds=("client",),
        desktop_session_check=_supports_desktop_session,
        new_user_defaults=_new_user_defaults,
    )
