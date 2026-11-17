---
name: yuque-local
description: 通过本机已配置的语雀 MCP 或官方 CLI 搜索、读取、总结、新建和更新语雀文档，管理知识库与目录。用于用户要求操作其语雀或提供语雀链接的任务。
---

# 语雀本地操作

复用本机连接，按用户任务操作真实语雀。常规任务直接使用本 skill，无需重读官方手册、重新安装或配置 key。

## 连接与工具选择

- 优先用当前可调用的 `yuque` / `yuque-local` MCP 工具，以实际 schema 为准。
- MCP 工具未加载时，用本 skill 的 `scripts/mcp_call.mjs` 调用现有本地 MCP；搜索分页、全量列表、版本历史、目录调整可用官方 CLI。
- CLI：`~/.config/yuque/bin/yuque`；MCP 启动器：`~/.config/yuque/bin/yuque-mcp`。均由 bridge 读取本地凭证，不必手动传 key。
- 使用本机已配置的账号；个人站点通常为 `https://www.yuque.com`。账号未知时用 `auth status` 或 `yuque_get_user` 取得 login，后续复用；仅在跨账号或认证异常时重查。
- 不读取、展示、复制或提交 `~/.config/yuque/credentials.json`；不输出 key，不通过 `--token`、shell 命令或聊天传递 key，不展示整个 Codex 配置。

```sh
~/.config/yuque/bin/yuque auth status
node ~/.codex/skills/yuque-local/scripts/mcp_call.mjs call yuque_get_user
# 仅在缺少参数说明或接口变化时查询特定 schema
node ~/.codex/skills/yuque-local/scripts/mcp_call.mjs list-tools --tool yuque_update_doc
```

需要恢复连接时才读 [补充操作](references/operations.md) 的“接入恢复”。

## 定位、搜索和读取

- 文档链接 `https://www.yuque.com/<owner>/<book>/<doc>` → `repo_id=owner/book`、`doc_id=doc`；知识库链接只有前两段。去掉 query/fragment，不把标题当 slug。分享短链或特殊路由先解析目标，不猜 namespace。
- `repo_id` 接受数字知识库 ID 或 namespace；`doc_id` 接受数字文档 ID 或 slug。取得数字 ID 后优先复用，改 slug 后仍可定位。
- 给出明确链接就直接读目标；只有名称时先搜索，再读相关正文。不能把搜索摘要当全文。无结果时尝试短关键词或同义词，再说明范围与缺口。
- 搜索结果可能为数组或 `items` 包装；namespace/slug 可能位于 `target.book.namespace` / `target.slug`，按实际返回提取。

| 任务 | MCP 参数 / CLI |
| --- | --- |
| 搜文档 | `yuque_search {query, type:"doc"}` |
| 搜知识库 | MCP `type:"repo"`；CLI `search '词' --type book --json` |
| 列知识库 | `yuque_list_books {login:"<login>"}`；全量用 CLI `book list <login> --all --json` |
| 列文档 | `yuque_list_docs {repo_id}`；全量用 CLI `doc list <owner/book> --all --json` |
| 读正文 | `yuque_get_doc {repo_id, doc_id, format:"markdown"}` |
| 读原始格式 | `yuque_get_doc {repo_id, doc_id, format:"lake", include_lake:true}` |
| 读目录 | `yuque_get_toc {repo_id}` 或 CLI `toc get <owner/book> --json` |

```sh
~/.config/yuque/bin/yuque search '关键词' --type doc --scope 'owner/book' --page 2 --json
node ~/.codex/skills/yuque-local/scripts/mcp_call.mjs call yuque_get_doc --args-json '{"repo_id":"owner/book","doc_id":"slug","format":"markdown"}'
```

旧 MCP 列表和搜索未必支持分页，`yuque_list_docs` 虽称 “all” 实际可能只取一页。需要完整清单时用 CLI `--all`，搜索用 `--page`；不能将一页条数报告为总数。

总结单篇依据实际正文；概览知识库先读目录与清单，再按任务选读重点文档并说明覆盖范围。附来源链接，保留冲突来源与更新时间。只要求总结时在聊天回答；保存回语雀需有相应指令。

## 新建与更新

1. 新建前确认目标知识库；修改前读目标文档，核对知识库、标题、ID、格式及需保留内容。用户明确的写入要求即授权，不重复询问常规修改。
2. 正文写入是**整篇替换**，不是 section patch。局部修改或追加时，在最新正文上合并后发送完整正文，保留不相关段落、链接和资源引用。
3. Markdown 正文更新用 MCP `yuque_update_doc {repo_id,doc_id,body,format:"markdown"}`，走 YMD/YFM 接口；**标题、slug、可见性另一次调用**，只带需改字段。本机 CLI 1.1.0 的 `doc update --body-file` 走 legacy API，不能当作 YMD 更新的等价替代。
4. 含画板、Mermaid、嵌入卡片、复杂表格等 Lake 内容时，先读 `format:"lake",include_lake:true` 核对原始结构，不将不完整 Markdown 导出覆盖回去。无法保留结构时先解决格式适配。
5. 新建用 `yuque_create_doc {repo_id,title,body,format:"markdown"}`，或 CLI `doc create <book> --title '标题' --body-file <绝对路径> --format markdown --json`。按用户要求设置可见性；未指定时采用私有 `public:0`，不主动公开。
6. 写后读取确认正文、元数据和最终链接。需要目录位置时检查 TOC：工具版本可能自动追加，也可能不追加；已存在则不重复建节点。调整目录见 [补充操作](references/operations.md)。

多行正文用程序生成 JSON 参数文件，供 helper 的 `--args-file` 读取，避免 shell 插值：

```python
import json
from pathlib import Path
payload = {"repo_id": "owner/book", "doc_id": 123,
           "body": Path("/absolute/path/revised.md").read_text(), "format": "markdown"}
Path("/absolute/path/yuque-args.json").write_text(json.dumps(payload, ensure_ascii=False))
```

```sh
node ~/.codex/skills/yuque-local/scripts/mcp_call.mjs call yuque_update_doc --args-file /absolute/path/yuque-args.json
```

Helper 的 `call` 真实执行操作，没有 dry-run。只执行当前任务授权范围；删除、公开、成员权限、整库重排须有具体范围授权，已有明确授权时不另加确认流程。

## 失败与回执

- 检查 `isError` 和全部 `content`，包括“创建成功但目录追加失败”。helper 成功退出 `0`，工具/连接失败非零。
- 写入超时或网络中断后先读取/搜索确认是否生效，再决定重试，避免重复创建。同一方法失败两次后换路径或指出缺失事实。
- 401/403 核对权限、有效期、站点；404 核对 namespace/slug/ID；429 按返回要求等待。CLI 内置部分退避，不叠加无界重试。
- 回执写明变更、验证结果和语雀链接；未测试写入、目录未同步等分别说明，不把连接注册当成业务成功。

## 按需扩展与来源

目录、知识库设置、历史版本、小记、画板、能力边界、接入恢复：只读 [references/operations.md](references/operations.md) 的相关部分。

依据本机 CLI **1.1.0**、MCP **1.0.0** 已安装源码、`--help` 和连接实测（2026-11-17）。仓库主线可能领先同版本已安装包；只有命令不匹配、缺少能力或版本变化时，再查相关 schema/`--help`/官方页面。

官方来源：[CLI](https://github.com/yuque/yuque-open-cli)、[MCP 能力](https://github.com/yuque/yuque-mcp-server/blob/main/docs/capability-scope.md)、[知识工作 Skills](https://github.com/yuque/yuque-ecosystem/tree/main/skills)。
