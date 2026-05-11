# Task #40 — 「探索」→「洞见」重命名 + 内部 Sub-tab 结构

## 目标

将顶层 Tab「🔍 探索」重命名为「🪞 洞见」，并在其内部建立三个 sub-tab 框架：检索、情绪趋势、洞察报告。后两个 sub-tab 本任务只建结构占位，功能由 task-42/43 填充。

## 必读契约

- `docs/api/components.md` # tab_search.py 节
- `docs/api/core.md` # state.py 节

## 改动范围

- **新增**：`components/tab_insight.py`（新 Tab 入口，内含 sub-tab 框架）
- **修改**：`app.py`（Tab 名称常量 + import 替换）
- **修改**：`components/tab_home.py`（主页模块卡片文案 + icon 更新）
- **修改**：`core/state.py`（新增 `insight_sub_tab` 键）
- **修改**：`docs/api/components.md`
- **修改**：`docs/api/core.md`
- **不许碰**：`components/tab_search.py`（内部逻辑不变，仍作为组件被调用）

## 接口约定

### app.py

`_TAB_SEARCH = "🔍 探索"` → `_TAB_INSIGHT = "🪞 洞见"`，其余导航逻辑不变。import 从 `render_search_tab` 改为 `render_insight_tab`。

### components/tab_insight.py — 新建

`render_insight_tab() -> None`
- 渲染三个 sub-tab，通过 `insight_sub_tab` session_state 驱动（与记录台子页同模式）：
  - **🔍 检索**：直接调用现有 `render_search_tab()`
  - **🌈 情绪趋势**：本任务渲染 `st.info("情绪趋势功能即将上线")`
  - **📋 洞察报告**：本任务渲染 `st.info("洞察报告功能即将上线")`

### state.py 新增键

| key | 默认值 | 说明 |
|---|---|---|
| `insight_sub_tab` | `"🔍 检索"` | 洞见 Tab 当前激活的 sub-tab |

### tab_home.py

将「🔍 探索」模块卡片更新为：
- 标题：`🪞 洞见`
- 说明文案：「智能检索历史记录，追踪情绪变化趋势，生成个人洞察报告——深度读懂你自己。」

## 不要做

- 不要修改 `tab_search.py` 的任何内容
- 不要在本任务实现情绪趋势或洞察报告功能
- 不要修改 `_HOME_TARGETS` 中的 `"search"` 旧键（保留向后兼容，另外追加 `"insight"` 键指向新 Tab）

## 验收清单

- [ ] 顶层第三个 Tab 显示「🪞 洞见」
- [ ] 洞见 Tab 内有三个 sub-tab，检索功能与之前完全一致
- [ ] 情绪趋势 / 洞察报告 sub-tab 显示占位提示
- [ ] 主页模块卡片文案已更新
- [ ] `insight_sub_tab` 已在 state.py 登记
- [ ] 已同步更新 `docs/api/components.md` + `docs/api/core.md`
- [ ] commit message 符合 AGENTS.md 规范
- [ ] git worktree 分支 push，**未** push main
