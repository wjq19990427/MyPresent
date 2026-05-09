# Task #32 — 导航机制改造（session_state 驱动，支持编程跳转）

## 目标

将 `app.py` 外层 `st.tabs` 替换为 `session_state` 驱动的自定义导航控件，使任意组件可通过设置 `_nav_target` 实现跨 Tab 跳转 + 内层 sub-tab 指定，同时保持视觉外观与现有 Tab 一致。

## 必读契约

- `docs/api/components.md` # `app.py` 结构说明
- `docs/api/core.md` # `state.py` 节

## 改动范围

- **修改**：`app.py`
- **修改**：`core/state.py`
- **修改**：`docs/api/core.md`
- **不许碰**：任何 `components/` 组件的内部逻辑

## 接口约定

### session_state 新增键（state.py 登记）

| key | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `active_tab` | `str` | `"🏠 主页"` | 当前激活的外层 Tab 名称 |
| `active_sub_tab` | `dict[str, str]` | `{}` | 各外层 Tab 的内层激活 sub-tab，key 为外层 Tab 名 |
| `_nav_target` | `tuple \| None` | `None` | 跳转指令；格式：`(外层Tab名, 子Tab名或None)`；被消费后立即置 `None` |

### 跳转协议

任意组件需要跳转时：
```
st.session_state["_nav_target"] = ("📝 记录台", "⬆️ 上传")
st.rerun()
```

`app.py` 在每次渲染时检测并消费 `_nav_target`：
- 将目标写入 `active_tab` / `active_sub_tab`
- 清空 `_nav_target = None`

### app.py 导航控件行为

- 外观：横向排列的按钮组，选中项有视觉高亮，与原 `st.tabs` 外观相近
- 选中由 `active_tab` 控制，点击按钮更新 `active_tab` 并 `st.rerun()`
- 记录台内层 sub-tab 同理，由 `active_sub_tab["📝 记录台"]` 控制

## 不要做

- 不要改变六个 Tab 的名称、顺序、对应组件
- 不要改任何 `components/` 内部逻辑
- 不要在导航控件里加任何业务判断（如"未完成记录提示"）

## 验收清单

- [ ] 六个 Tab 可正常点击切换，功能与改造前一致
- [ ] 记录台内三个 sub-tab 可正常切换
- [ ] `st.session_state["_nav_target"] = ("📝 记录台", "⬆️ 上传"); st.rerun()` 可正确跳转到上传页
- [ ] 刷新页面后默认回到主页（`active_tab` 默认值）
- [ ] 已同步更新 `docs/api/core.md`（state.py 新键登记）
- [ ] commit message 符合 AGENTS.md 规范
- [ ] git worktree 分支 push，**未** push main

## 架构师备注

`_nav_target` 消费必须在渲染导航控件**之前**完成（先更新 `active_tab`，再渲染按钮），否则高亮与内容会差一帧。`active_sub_tab` 用 dict 而非单一字符串，是为了各 Tab 的子页选择互不干扰（用户在规划台选了日历，切到记录台再切回时子页状态保留）。
