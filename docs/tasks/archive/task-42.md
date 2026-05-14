# Task #42 — 情绪趋势热力矩阵 UI

## 目标

在「🪞 洞见」的「🌈 情绪趋势」sub-tab 中，实现基于 plotly 的情绪热力矩阵：行为情绪类型，列为时间周期，单元格颜色深浅反映该情绪在该时段的强度；支持快速/精准两种评分模式，支持时间粒度切换，点击单元格可下钻到对应记录。

**依赖**：task-40（洞见 Tab 结构）+ task-41（EmotionScoringSkill）均已合并。

## 必读契约

- `docs/api/components.md` # tab_insight.py 节
- `docs/api/skills.md` # EmotionScoringSkill 节
- `docs/api/core.md` # db_manager.py::Session CRUD 节

## 改动范围

- **修改**：`components/tab_insight.py`（填充「情绪趋势」sub-tab，替换占位内容）
- **修改**：`docs/api/components.md`
- **不许碰**：`skills/emotion_scoring_skill.py`（只调用，不修改）

## 接口约定

### 筛选与控制区（独立于归档页，渲染在热力矩阵上方）

- **时间范围**：开始日期 + 结束日期，date_input，默认最近 3 个月
- **时间粒度**：单选 `week / month / year`，按钮切换，决定矩阵的列数
- **评分模式**：单选 `快速（频次）/ 精准（LLM）`，默认快速；切换到精准时提示「精准模式将消耗 LLM 调用，首次计算后缓存」
- **数据范围**：仅使用 `status == 'final'` 的记录；按 `content_time`（可解析时）优先，否则 `upload_time` 落在所选时间范围内

### 热力矩阵

- **行**：当前筛选结果中所有 session 的 `emotion_tags` 取并集，每种情绪一行；无情绪数据时提示引导用户先完善标签
- **列**：时间周期（按粒度划分），格式：`2026-W18`（周）/ `2026-04`（月）/ `2026`（年）
- **单元格值**：该情绪在该时段所有 session 中的平均 score（快速 or 精准模式的缓存值），空值显示为 0
- **颜色方案**：每种情绪对应固定基础色（从 `label_registry` 中的情绪标签按顺序分配一组预设颜色列表），色调固定、深浅表强度（0=最浅，1=最深）；用 plotly 的 `go.Heatmap` + 自定义 colorscale 实现
- **交互**：点击单元格 → 在矩阵下方展示该时段含该情绪标签的 session 卡片列表（调用 `_render_card`）

### 颜色预设

为 9 个默认情绪标签（喜悦/平静/充实/期待/疲惫/焦虑/愤怒/失落/迷茫）各分配一个基础色（hex），用户新增情绪时从备用色池循环取色。颜色列表在组件内部定义为常量，无需写入 DB。

### 精准模式触发

点击「开始精准分析」按钮（精准模式下显示）→ 调 `EmotionScoringSkill().score_precise(sessions, model_id)` → `st.spinner` 提示 → 完成后矩阵自动刷新。已缓存的 session 不重算（Skill 内部处理）。

## 不要做

- 不要在快速模式下调用 LLM
- 不要在 UI 层直接操作 `emotion_scores` 表，通过 Skill 和 `get_emotion_scores` 访问
- 不要在矩阵上实现跨情绪颜色混合

## 验收清单

- [ ] 「情绪趋势」sub-tab 不再显示占位文字，显示筛选区 + 热力矩阵
- [ ] 快速模式下切换时间范围/粒度后矩阵即时刷新，无 LLM 调用
- [ ] 矩阵行数等于筛选结果中 `emotion_tags` 的并集数量
- [ ] 点击单元格后矩阵下方显示该时段含该情绪的记录卡片
- [ ] 精准模式点击「开始精准分析」后有 spinner，完成后矩阵颜色更精细
- [ ] 无有效记录时显示友好空态提示
- [ ] 已同步更新 `docs/api/components.md`
- [ ] commit message 符合 AGENTS.md 规范
- [ ] git worktree 分支 push，**未** push main

## 架构师备注

plotly `go.Heatmap` 不原生支持每行不同 colorscale，推荐方案：对每种情绪分别生成一个单行 `go.Heatmap` trace，设置各自的 colorscale（白→情绪基础色），叠加到同一个 `go.Figure` 中，行之间加间距。点击事件通过 `st.plotly_chart(use_container_width=True)` 返回的 `event` 对象获取（Streamlit 1.33+ 支持 `on_select`）。若当前 Streamlit 版本不支持 plotly 点击事件，可退化为在矩阵上方渲染时段下拉选择器来驱动下钻。
