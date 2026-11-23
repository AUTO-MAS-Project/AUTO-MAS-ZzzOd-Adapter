"""绝区零一条龙迁移期间由宿主使用的只读服务。"""

from auto_mas_core import BasePlugin

from .launchers import find_launcher_exe, resolve_launcher
from .tools.catalog import list_app_catalog


class ZzzOdPreviewPlugin(BasePlugin):
    """提供宿主调度与配置页使用的启动器选择和任务目录。"""

    provides_services = {
        "zzzod.catalog": "read_catalog",
        "zzzod.find_launcher": "find_launcher",
        "zzzod.resolve_launcher": "select_launcher",
    }
    read_catalog = staticmethod(list_app_catalog)
    find_launcher = staticmethod(find_launcher_exe)
    select_launcher = staticmethod(resolve_launcher)
