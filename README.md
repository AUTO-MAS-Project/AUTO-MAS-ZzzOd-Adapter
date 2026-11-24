<!-- auto-mas:i18n
{
  "display_name_i18n": {
    "zh_CN": "绝区零一条龙专项",
    "en": "Zenless Zone Zero OneDragon",
    "ja": "ゼンレスゾーンゼロ OneDragon"
  },
  "description_i18n": {
    "zh_CN": "绝区零一条龙专项适配器，支持托管、账号配置、自动代理和备份恢复。",
    "en": "Zenless Zone Zero OneDragon adapter for managed scripts, account configuration, automated runs, and backup recovery.",
    "ja": "ゼンレスゾーンゼロ OneDragon の管理、アカウント設定、自動実行、バックアップ復元に対応するアダプターです。"
  },
  "tags_i18n": {
    "zh_CN": ["专项适配", "绝区零"],
    "en": ["Script adapter", "Zenless Zone Zero"],
    "ja": ["専用アダプター", "ゼンレスゾーンゼロ"]
  }
}
-->

# AUTO-MAS 绝区零一条龙专项

绝区零一条龙专项已可在配套的 AUTO-MAS 源码宿主中使用。独立配置和原生直控已分别完成一轮实机代理，新建实例及配置导入已核对落盘。当前以源码联调为主，公开发行和市场安装验收待完成。

## 已实现

- 托管和账号配置接管，支持共享配置、独立配置及原生直控。
- 自动代理支持单实例和多实例调度。同一设备可成组运行，不同设备依次执行。保留普通代理结果汇总和账号统计。
- 支持启动器选择、任务目录、原生配置与只看会话，以及原生实例管理、槽位管理、备份和恢复。
- 通过配套宿主提供专项 HTTP API 和 MCP 工具，继续使用 MAS 现有的托管与账号编辑页面。

## 源码联调

将本仓库的 `refactor/zzzod-plugin-migration` 分支检出到配套 AUTO-MAS 源码工作区的 `plugins/zzzod_adapter`。建议使用独立测试配置。接管存量配置前备份 `config/` 和 `data/data.db`。

在宿主的 `refactor/zzzod-plugin-migration` 分支上，启动开发环境前设置 `$env:AUTO_MAS_ZZZOD_ADAPTER = '1'`，由宿主启用插件并交接托管。关闭开关时，插件仅提供任务目录和启动器选择。若存量托管已经交接，回退前先停止 MAS 并恢复切换前的配置和数据库，再清除开关。

宿主的 `refactor/zzzod-plugin-cutover` 是移除内置后端的本地验证分支，现有托管可触发插件安装或启用。该分支使用 `0.1.1` 或更新的候选包，可识别并升级早期的 `0.1.0` 预览包。

正式标签 `v5.9.0-beta.1` 缺少完整接管需要的 `task_client` 和 `task_process_context`。联调须使用包含这两个 SDK 接口的配套宿主。

## 待接入与发布

- **LogFlow 节点详情** · 已预留日志采集、收尾和托管报告接入位。待 [AUTO-MAS #2072](https://github.com/AUTO-MAS-Project/AUTO-MAS/pull/2072) 合入后接入，并核对详情和通知。
- **专项页面与桌面 IPC** · 当前由配套 MAS 宿主提供。待通用插件前端与桌面扩展点可用后迁出。
- **公开发行** · 确认配套宿主版本及 `auto-mas-core` 依赖下限，完成市场安装、重启、存量接管及 Runtime 远端升级验收。插件发布并完成验收后，MAS 主仓再单独清理内置后端。

## 本地构建

在本仓库根目录构建并检查 wheel 和源码包。

```powershell
uv build
uvx twine check --strict dist/*.whl dist/*.tar.gz
```
