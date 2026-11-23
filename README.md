<!-- auto-mas:i18n
{
  "display_name_i18n": {
    "zh_CN": "绝区零一条龙",
    "en": "Zenless Zone Zero OneDragon",
    "ja": "ゼンレスゾーンゼロ OneDragon"
  },
  "description_i18n": {
    "zh_CN": "绝区零一条龙专项适配器，支持托管、账号配置、自动代理和备份恢复。",
    "en": "Zenless Zone Zero OneDragon adapter for managed scripts, account configuration, automated runs, and backup recovery.",
    "ja": "ゼンレスゾーンゼロ OneDragon の管理、アカウント設定、自動実行、バックアップ復元に対応するアダプターです。"
  },
  "tags_i18n": {
    "zh_CN": ["专项", "迁移预览"],
    "en": ["Adapter", "Migration preview"],
    "ja": ["アダプター", "移行プレビュー"]
  }
}
-->

# AUTO-MAS 绝区零一条龙适配器

迁移测试版。使用配套的 AUTO-MAS 源码分支，将源码插件放在 `plugins/zzzod_adapter`。在启动应用前设置 `AUTO_MAS_ZZZOD_ADAPTER=1`，宿主会在打开配置前启用插件并交接现有托管。使用独立测试配置，或在切换前备份现有配置。

插件接管托管和账号配置、自动代理、原生配置和只看会话、备份恢复。节点通知等待 LogFlow 接入。关闭开发开关后，宿主使用内置专项，此时启用插件只会接入任务目录和启动器选择服务。
