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

迁移测试版。使用配套的 AUTO-MAS 源码分支，将源码插件放在 `plugins/zzzod_adapter`。使用独立测试配置，或在切换前备份现有配置。

- `refactor/zzzod-plugin-migration` 保留内置专项。在源码启动前设置 `AUTO_MAS_ZZZOD_ADAPTER=1`，宿主会启用插件并交接现有托管。清除开关前先停掉 MAS 并恢复旧配置。
- `refactor/zzzod-plugin-cutover` 已移除内置专项。已有托管会触发插件安装或启用。空白配置可在插件中心启用，开发环境也可设置上述开关要求自动安装。

插件接管托管和账号配置、自动代理、原生配置和只看会话、备份恢复。节点通知等待 LogFlow 接入。在保留内置专项的迁移分支上关闭开发开关后，启用插件只会接入任务目录和启动器选择服务。

## 本地构建

在本仓库根目录构建并检查 wheel 和源码包。

```powershell
uv build
uvx twine check --strict dist/*.whl dist/*.tar.gz
```

首发前用实际配套的宿主发行版验证 wheel，并按其 SDK 版本修订 `auto-mas-core` 最低版本。`5.9.0b1` 是当前联调宿主的版本标识，正式标签 `v5.9.0-beta.1` 缺少迁移新用到的 `task_client` 和 `task_process_context`，仅凭版本号无法确认完整接管兼容性。完成发包之后，再交付移除内置专项的宿主版本。
