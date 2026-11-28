"""将插件配置、执行器和专项路由注册到 MAS。"""

from dataclasses import fields

from auto_mas_core import ScriptAdapterPlugin, ScriptEntry, ScriptTypeDecl
from fastapi import APIRouter

from .api import panel_router, router
from .config import ZzzOdConfig, ZzzOdUserConfig
from .expander import ZzzOdExpander
from .tools.restore_service import RESTORE_POOLS

_api = APIRouter()
_api.include_router(router, prefix="/api/scripts", tags=["脚本管理"])
_api.include_router(router, prefix="/api/plugin/zzzod_adapter", include_in_schema=False)
_api.include_router(panel_router, prefix="/api/plugin/zzzod_adapter")


def _desktop_session_reason(_config: ScriptEntry, elevated: bool):
    return None if elevated else "admin_required"


def _new_user_defaults() -> dict:
    return {"Info": {"Base": "native", "IfQuickConfig": False}}


_user_defaults = (
    {"new_user_defaults": _new_user_defaults}
    if any(field.name == "new_user_defaults" for field in fields(ScriptTypeDecl))
    else {}
)


class ZzzOdAdapter(ScriptAdapterPlugin):
    script_type_key = "ZzzOd"
    api_router = _api
    decl = ScriptTypeDecl(
        script_type=ZzzOdConfig,
        user_type=ZzzOdUserConfig,
        expander_class=ZzzOdExpander,
        activity_game="zenless",
        game_kinds=("client",),
        desktop_session_check=_desktop_session_reason,
        restore_pools=tuple(RESTORE_POOLS),
        **_user_defaults,
    )
