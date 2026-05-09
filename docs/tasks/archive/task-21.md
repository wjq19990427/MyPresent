# Task #21 — 年度规划分类管理：动态增删 + 系统默认保护

## 目标

将年度规划的分类标签从硬编码常量改为数据库驱动，支持用户在 UI 中动态添加、删除自定义分类；四个系统内置分类受保护，不可被用户删改。

## 依赖

**必须在 task-19 和 task-20 均合并后执行。**

## 必读契约

- `docs/api/core.md` # `goal_categories` 相关函数（task-19 新增的 `get_goal_categories` / `add_goal_category` / `delete_goal_category`）
- `docs/api/components.md` # `tab_planning.py` 节（task-20 更新后的年度规划骨架）

## 改动范围

- **修改**：`components/tab_planning.py`（`_render_annual_goals` 及新增分类管理区）
- **修改**：`core/state.py`（新增分类管理面板展开状态键）
- **更新**：`docs/api/components.md`（更新 `tab_planning.py` 节）
- **不许碰**：`core/db_manager.py` / `app.py` / 日历待办相关函数

## 接口约定

### 分类来源切换

`_render_annual_goals` 中所有引用 `GOAL_CATEGORIES` 的地方改为运行时调用 `get_goal_categories()`——筛选器、表单下拉均从 DB 动态获取，不再 import 硬编码常量。

---

### `_render_category_manager() -> None`
- 行为：渲染可展开/折叠的分类管理面板；系统内置分类有受保护标记且无删除入口；用户自定义分类可删除；面板底部支持新增分类
- 副作用：增删后 rerun，筛选器与表单下拉框即时反映变化
- 约束：添加与系统内置同名的分类时显示警告，不写库；`is_system` 判断来自 DB，不在 UI 层硬编码分类名称

## 不要做

- 不要修改日历待办相关函数
- 不要修改 `app.py`
- 不要在 UI 层硬编码系统内置分类名称（从 `get_goal_categories()` 的 `is_system` 字段判断）

## 验收清单

- [ ] `python -c "import app, core, skills, components"` 通过
- [ ] `streamlit run app.py` 启动无报错
- [ ] 年度规划筛选器与表单下拉框显示 DB 中的实际分类（含用户新增）
- [ ] 分类管理面板可展开/折叠
- [ ] 系统内置分类有保护标记，无删除入口；用户自定义分类可删除
- [ ] 添加新分类 → 即时出现在筛选器和表单下拉框
- [ ] 删除自定义分类 → 即时从选项移除；已有目标的 `category` 字段保留原值不受影响
- [ ] 添加与系统内置同名的分类时显示警告，不写库
- [ ] `docs/api/components.md` 已更新
- [ ] commit 符合规范（建议 `feat(tab_planning): 年度规划分类动态管理 · 关联 #21`）
- [ ] worktree 分支提交，未 push main

## 架构师备注

- `get_goal_categories()` 每次 rerun 调用，无需缓存（轻量查询）
- 删除分类不级联更新已有目标的 `category` 字段，属有意设计：历史记录保留原始分类名，本期不处理孤立分类值问题
