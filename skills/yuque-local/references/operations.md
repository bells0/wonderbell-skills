# 语雀补充操作

仅在任务涉及相应能力时读取对应部分。下文 `yuque` 均指 `~/.config/yuque/bin/yuque`，不是另一套全局命令或临时 npx。依据本机 CLI 1.1.0、MCP 1.0.0（2026-11-17）。

## 目录与知识库

先 `yuque toc get <book> --json` 获取现有节点 UUID。移动/编辑使用节点 UUID，不能用文档 ID 代替。

```sh
# 添加已有文档；先确认尚未在目录中
yuque toc update owner/book --action appendNode --action-mode child --target-uuid '' --type DOC --doc-ids 123 --json
# 创建分组
yuque toc update owner/book --action appendNode --action-mode child --target-uuid 'parent-uuid' --type TITLE --title '分组名' --json
# 移动已有节点
yuque toc update owner/book --action appendNode --action-mode child --target-uuid 'parent-uuid' --node-uuid 'existing-node-uuid' --json
yuque toc update owner/book --action editNode --node-uuid 'node-uuid' --title '新标题' --json
```

`appendNode`/`prependNode` + `--node-uuid` 表示移动，不带它表示新建。DOC 用 `--doc-ids`（逗号分隔）；TITLE 要 `--title`；LINK 要 `--title` 和 `--url`。`removeNode` 移除目录节点，不能据此声称文档已删除。`book update --toc` 替换整份目录，普通移动不用它。

MCP `yuque_update_toc {repo_id,toc_data}` 的 `toc_data` 是**单个操作对象的 JSON 字符串**，不是节点数组。旧 MCP 自动追加实现使用 `doc_id`，CLI 推荐 `doc_ids`；需要稳定位置时用以上 CLI 参数并读取验证。

```sh
yuque book get owner/book --json
yuque book create <login> --name '知识库名' --slug 'book-slug' --public 0 --json
yuque book update owner/book --name '新名称' --description '简介' --json
```

团队知识库列表/新建用 CLI `--group`。`book list <login> --filter-by-ability create_doc --all --json` 可筛选有写入能力的库。可见性 CLI 值为 `0` 私有、`1` 公开、`2` 组织内，须符合用户要求和空间能力。

## 文档与历史版本

```sh
yuque doc get owner/book doc-slug --json
yuque doc get 123 --meta
yuque doc list owner/book --all --json
yuque doc list owner/book --changed-at-gte '2026-11-01T00:00:00+08:00' --all --json
yuque doc versions 123 --json
yuque doc version 456 --json
```

CLI `doc get` 默认输出正文，`--meta` 选定元数据，`--json` 完整对象。其读取走 legacy API，与 MCP YMD 视图可能不同，现代 Markdown 用 MCP 正文流程核对。`body` 为空不等于文档为空：检查 `format`、`body_lake`、`body_sheet`、`body_table`。sheet/table 不属于普通 Markdown 写入支持范围。

版本命令最多列出最近 100 个已发布版本，不是完整编辑草稿历史。恢复历史内容也是一次真实写入，须符合用户请求范围。

## 小记与画板

使用 MCP，CLI 无等价子命令；缺少参数时只查询对应 `list-tools --tool <name>`。

| 操作 | 参数要点 |
| --- | --- |
| `yuque_list_notes` | `page`、`limit`、可选 `status`；检查 `has_more`；合并多页时按 ID 去重置顶条目 |
| `yuque_get_note` | 数字 `note_id` |
| `yuque_create_note` | `body` |
| `yuque_update_note` | `note_id`、完整 `body`；先读后合并，不用摘要覆盖全文 |
| `yuque_get_resource` | `resource_type:"board"`、`resource_id`、`doc_id`/`url` 二选一 |
| `yuque_create_resource` | `resource_type:"board"`、定位二选一、`type`、字符串 `dsl`；可选 `insert_after_lake_id` |
| `yuque_update_resource` | `resource_type:"board"`、`resource_id`、定位二选一；`text`/对象 `dsl` 二选一 |

画板类型只有 `mindmap`、`flowchart`、`architecturediagram`。`resource_id` 不含 `board://`。先读取现有画板，再改 DSL，不替换整篇 Lake 文档。新建未传 `insert_after_lake_id` 时追加文档末尾。

## 团队、删除与能力边界

CLI 另有 `user groups`、`group members`、`stats group|members|books|docs`；任务需要时只查相应 `--help`。成员和角色修改须有对具体对象、权限的授权。

`doc delete`、`book delete`、`group member remove` 在非交互脚本中须传 `--yes`，只有用户明确授权具体范围时使用。不用删除或权限操作做连接自检。

MCP 稳定工具面没有评论读写、附件上传/文件管理、成员权限管理、分段读取或增量 section update。`resource` 只支持画板，不能当任意附件上传接口。需要这些能力时核对官方对应接口或使用用户授权的浏览器路径，不虚构命令。

## 接入恢复

仅在入口不存在、认证失败或服务器无法启动时使用。

- 连接目录 `~/.config/yuque/`；bridge/bin/runtime 是工具，`connection.json` 是非密钥连接摘要。不要读取 `credentials.json`。
- 用户自行在 `~/.codex/config.toml` 的 `[shell_environment_policy.set]` 设置 `YUQUE_TOKEN`，个人站点无需 `YUQUE_HOST`。不让用户在聊天发 key；检查变量只输出是否存在。
- 此 skill 复用已有本地 bridge，不打包账号凭证或自动安装连接器。已有部署脚本时按其 `--help` 恢复；部署脚本缺失时先说明依赖缺口，再依照官方 CLI/MCP 文档恢复本机连接，不能猜测其他项目的安装路径。若需从既有 Codex shell set 读取变量，可用 Python 3.12 `tomllib` 传入子进程环境，不输出值。
- 本机 bridge 部署需要验证账号并注册 MCP；helper 依赖 Node.js 20+、`~/.config/yuque/bin/yuque-mcp` 及 `~/.config/yuque/runtime` 内的 MCP SDK。凭证继续由原有连接器管理，不复制到 skill 目录。
- bridge 同时映射 CLI 的 `YUQUE_TOKEN` 和旧 MCP 的 `YUQUE_PERSONAL_TOKEN`。本机 MCP 1.0.0 使用旧 `YUQUE_BASE_URL`，bridge 目前清除此变量；实测是个人默认站点。迁往企业/私有站点前须修正并验证 host 映射，不能只设置 `YUQUE_HOST` 就声称 MCP 已接通。
- 恢复后用 `auth status` 和一次只读知识库列表验证。不把重装或环境巡检变成每次操作前置步骤。

CLI 退出码：`0` 成功、`1` API/未知错误、`2` 用法错误、`3` 认证、`4` 资源不存在、`5` 限流；helper 非零退出不沿用此分类。

## 来源与维护

- [官方 CLI](https://github.com/yuque/yuque-open-cli) 及已安装包的 `README.zh-CN.md`、`dist/commands`、`dist/client/api`。
- [官方 MCP](https://github.com/yuque/yuque-mcp-server) 及本机 `dist/tools`、`dist/services/yuque-client.js`。
- [能力说明](https://github.com/yuque/yuque-mcp-server/blob/main/docs/capability-scope.md) 的仓库主线可能领先已安装包，以当前 schema/行为判定参数。
- [官方知识工作 Skills](https://github.com/yuque/yuque-ecosystem/tree/main/skills) 另有智能搜索、摘要、日常记录、阅读消化、笔记整理、知识连接、陈旧检测、风格提取。本 skill 已覆盖常用搜索/摘要；专项工作流有需要再读对应 skill，不自动安装整套或自动改写知识库。
