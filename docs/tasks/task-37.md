# Task #37 — 分组管理升级（图库逻辑）

## 目标

将已归档 tab 升级为支持分组浏览：在「已归档」内新增视图切换（全部 / 分组），分组视图采用相册格布局；已归档批量模式新增「加入分组」操作；分组内支持移出记录。

**依赖**：task-35/36 先合并。

## 必读契约

- `docs/api/components.md` # tab_archived.py + cards.py 节
- `docs/api/core.md` # db_manager.py::Groups 节

## 改动范围

- **修改**：`components/tab_archived.py`
- **修改**：`components/cards.py`（批量模式新增「加入分组」）
- **修改**：`core/state.py`（新增 `archived_view_mode` / `archived_group_selected` 键）
- **修改**：`docs/api/components.md` / `docs/api/core.md`
- **不许碰**：`core/db_manager.py` Groups 相关函数签名

## 接口约定

### session_state 新增键（state.py 登记）

| key | 默认值 | 说明 |
|---|---|---|
| `archived_view_mode` | `"all"` | `"all"` 或 `"groups"` |
| `archived_group_selected` | `None` | 当前展开的分组 id；None 表示在分组列表 |

### tab_archived.py 视图切换

顶部新增两个按钮：「📋 全部」和「📁 分组」，驱动 `archived_view_mode`。

**全部模式**（现有逻辑，保留）：现有筛选 + 网格 + 批量操作。

**分组模式**：

```
层一：分组列表
├── [⊕ 新建分组] 按钮
├── 分组格子（st.columns，每行 3 个）
│   每格：封面缩略图（取第一条记录的缩略图，无则占位）
│          分组名称
│          记录数量
│          [✎ 改名] [🗑️ 删除] 图标按钮
└── 删除分组：仅删分组关联，不删记录（确认弹窗）

层二：分组详情（archived_group_selected 非 None）
├── [← 返回] 按钮
├── 分组名称标题
├── 网格展示该分组的所有 final 记录（同全部模式卡片）
└── 批量模式下新增「移出分组」操作
```

### 批量模式「加入分组」（全部模式）

在 `cards.py _render_batch_row` / `tab_archived.py` 批量操作区新增：
- 「📁 加入分组」按钮，点击后弹出分组选择（`st.selectbox` 或 inline 列表）
- 选择分组后调 `update_session_groups(sid, [...existing_gids, new_gid])` 逐条更新
- 支持一次性批量更新所有勾选记录

### 管理分组入口

原有管理分组 expander（在已归档全部模式内）保留，但仅保留「新建」和「删除」功能；改名/封面逻辑在分组格子里内联操作。

## 不要做

- 不要改 `get_groups / create_group / delete_group` 的签名
- 不要在分组视图里重新实现筛选（分组详情页只展示该组所有记录，不加维度筛选）
- 不要改 `update_session_groups` 调用以外的保存逻辑

## 验收清单

- [ ] 已归档顶部有「全部 / 分组」切换按钮，默认「全部」
- [ ] 分组模式展示分组格子，有记录数和封面缩略图（无则占位）
- [ ] 新建分组可用；删除分组后记录不丢失
- [ ] 点击分组进入详情，显示该组所有记录，有「← 返回」按钮
- [ ] 全部模式批量勾选后可「加入分组」，对话框选择目标分组
- [ ] 分组详情批量模式可「移出分组」
- [ ] 两个新 session_state 键已在 `state.py` 登记
- [ ] 已同步更新 `docs/api/components.md`
- [ ] commit message 符合 AGENTS.md 规范
- [ ] git worktree 分支 push，**未** push main

## 架构师备注

分组详情页的记录查询：调 `load_db()` 后按 `group_ids` 过滤（现有 session dict 已含 `group_ids`），不需要新增 DB 方法。封面缩略图取该分组第一条 final 记录的第一个图片文件，用现有 `video_thumbnail` / `PIL` 逻辑；无图片时展示分组名首字作为占位。
