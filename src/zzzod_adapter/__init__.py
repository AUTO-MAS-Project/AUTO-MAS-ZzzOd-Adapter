"""AUTO-MAS 绝区零一条龙专项。"""

from auto_mas_core import PLUGIN_API_VERSION, Config

from .plugin import ZzzOdPreviewPlugin

_registered = Config.ScriptConfig.entry_types.get("ZzzOdConfig")
if _registered is not None and _registered.__module__.startswith("app."):
    PLUGIN = ZzzOdPreviewPlugin
else:
    from .adapter import ZzzOdAdapter

    PLUGIN = ZzzOdAdapter

__all__ = ["PLUGIN", "PLUGIN_API_VERSION"]
