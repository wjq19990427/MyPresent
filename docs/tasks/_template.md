# Task #N — <短标题>

> 任务卡模板。复制本文件改名为 `task-N.md` 后填写。

## 目标

<1-2 句话写为什么做这个、做完之后用户/系统能看到的变化。不要写实现细节。>

## 必读契约

- `docs/api/core.md` # `<具体哪一节>`
- `docs/api/skills.md` # `<具体哪一节>`
- `docs/api/components.md` # `<具体哪一节>`

> 删除不相关项；最少保留 1 项。如果一个都没用上，先反思任务卡是不是定义错了。

## 改动范围

- **新增**：`<file path>`
- **修改**：`<file path>`
- **不许碰**：`<file path / 模块>`

## 接口约定

<描述新增/修改的公开函数或组件的行为契约，格式：>

`function_name(param: Type, ...) -> ReturnType`
- 行为：做什么（不是怎么做）
- 副作用：写库 / 改 session_state / 触发 rerun 等
- 约束：调用前提、禁止场景

> 不写伪代码或实现细节——实现工读现有代码后自行决定 How。
> 只在跨模块架构约束（如"必须在 st.form 外调用"）时才给提示。

## 不要做（防止画蛇添足）

- 不要顺手重构 `<X>`
- 不要给 `<Y>` 加缓存 / 重试 / 防御性检查
- 不要新增 `<Z>` 抽象层

## 验收清单

- [ ] 新签名/契约与任务卡一致
- [ ] `python -c "import app, core, skills, components"` 通过
- [ ] `streamlit run app.py` 启动无报错
- [ ] 手工跑通：<具体路径，例如「打开记录舱 → 上传图片 → 点 ✨ AI → 看到推荐标签」>
- [ ] 若改动了公开 API，已同步更新 `docs/api/*.md`
- [ ] commit message 符合 AGENTS.md 规范
- [ ] git worktree 分支 push，**未** push main

## 架构师备注

<可能的隐式依赖、相邻模块的副作用、历史踩坑、为什么选这种实现而非另一种。>
