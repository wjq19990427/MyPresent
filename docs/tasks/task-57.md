# Task-57：编辑面板内联化

## 变更说明

**类型**：UI 优化  
编辑记录时，AI 分析面板会以 expander 展开，造成视觉脱节、难以定位。本任务将 AI 分析面板改为内联展开块，点击按钮就地展开/收起，不再产生"额外窗口"感。同步将归档台"新建分组"的 expander 也改为内联按钮控制。

---

## 经全量审计确认的变更范围

**需改动：**
- `components/ai_analysis.py`：`_render_analysis_panel()` 中的 `st.expander("✨ AI 分析")` → session_state 控制的内联展开块
- `components/tab_archived.py`（约 366 行）：`st.expander("⊕ 新建分组")` → 按钮控制的内联展开块

**保持 expander（纯展示，不涉及编辑行为）：**
- `cards.py` 文件列表、编辑历史
- `tab_planning.py` 关联待办、月统计
- `tab_search.py` 模糊时间告警
- `tab_insight.py` 报告章节
- `tab_recycle.py` 内容预览
- `eval_dashboard.py` LLM 配置管理（管理面板）

---

## ai_analysis.py 改动行为

- 新增 session state 键 `_analysis_panel_open_{safe_state_key}`
  - 初始值：若 `keys["result"]` 已在 session_state 中（有历史结果）则为 True，否则 False
- 原 `with st.expander(...):` 整块替换为：
  - toggle 按钮（面板关闭时显示"✨ AI 分析"，展开时显示"▲ 收起 AI 分析"），点击切换 open 状态并 rerun
  - `if open_state:` 条件块，内容与原 expander 内完全一致
- `_run_analysis()` 在调用 `st.rerun()` 前将 open 键设为 True，确保分析完成后面板自动展开
- 公开函数 `render_ai_analysis()` / `render_session_ai_analysis()` 签名不变

## tab_archived.py 改动行为

- 新增 session state 键 `_archived_new_group_open`（bool，默认 False）
- 原 `st.expander("⊕ 新建分组"):` 替换为：
  - 按钮控制 open 键，展开/收起
  - `if _archived_new_group_open:` 条件块，内容与原 expander 内不变

---

## 已知约束

- L2 契约同步：`docs/api/components.md` 中 `render_ai_analysis` / `render_session_ai_analysis` 的渲染行为描述需同步更新（去掉 expander 相关描述）

---

## 验收（用户可见）

- [ ] 记录台详情页：点击"✨ AI 分析"按钮，分析面板就地展开，不跳转/不遮挡其他内容
- [ ] 再次点击同一按钮，面板收起
- [ ] AI 分析运行完成后，面板自动展开显示结果
- [ ] 归档台：点击"新建分组"按钮后，分组表单就地展开，不产生页面跳转
