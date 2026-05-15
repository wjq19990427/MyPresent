# Task-55：修改密码 + 系统页用户看板 UI 优化

## 变更说明

**类型**：新功能 + 优化  
登录用户可在「⚙️ 系统」页修改自己的密码（需验证原密码、二次确认新密码）；管理员用户看板从纯文字列表升级为更清晰的卡片式布局。

---

## 数据层

**`core/db_manager.py`**

新增 `update_user_password(username: str, old_password: str, new_password: str) -> None`：
- 用 `verify_user()` 验证原密码；原密码错误时抛 `ValueError("原密码错误")`
- 新密码去空白后为空时抛 `ValueError("新密码不能为空")`
- 验证通过后重新生成 salt，用 `_hash_password()` 散列新密码，写回全局库 `users` 表
- 副作用：写 `config.get_global_db_path()`；不影响其他字段

契约同步更新至 `docs/api/core.md`。

---

## UI 层

**`components/eval_dashboard.py`**

### 修改密码面板（新增）

渲染条件：`DEPLOY_MODE == "cloud"` 且用户已登录（`st.session_state.get("_current_user")` 非空）。  
位置：插入到系统页现有内容的适当位置，与其他面板风格一致（`st.divider()` + `st.subheader()`）。

表单字段：
- 原密码（`type="password"`）
- 新密码（`type="password"`）
- 确认新密码（`type="password"`）

提交前端校验（UI 层，不依赖 DB）：
- 新密码与确认密码不一致 → `st.error`，阻止提交
- 任一字段为空 → `st.error`，阻止提交

提交后调用 `update_user_password()`，捕获 `ValueError` 以 `st.error` 显示；成功后 `st.success("密码已修改")`，表单使用 `clear_on_submit=True` 自动清空。

### 用户看板 UI 优化

现有实现（`_render_admin_user_panel()`）：
- 用户列表只用 `st.write(username)` 逐行输出，样式简陋

优化要求：
- 显示用户总数（如 `已注册 N 位用户`）
- 每个用户以带边框的行或卡片展示，区分管理员（`is_admin=1`）与普通用户，管理员有明显标识（如徽章/标签）
- `list_usernames()` 需扩展为同时返回 `is_admin` 字段，或新增专用查询函数——由 Codex 决定最小改动方案

---

## 已知约束

- `local` 模式下无登录体系，两个新面板均不渲染
- 修改密码只操作当前登录用户自己的账户，不允许跨用户修改
- 管理员面板仍仅对 `is_admin=True` 用户可见；修改密码面板对所有已登录用户可见

---

## 验收（用户可见）

- [ ] cloud 模式已登录 → 系统页出现修改密码表单
- [ ] 原密码错误 → 提示"原密码错误"，不修改
- [ ] 新密码两次不一致 → 提示不一致，不提交
- [ ] 任意字段为空 → 提示必填，不提交
- [ ] 全部验证通过 → 密码修改成功，新密码可立即登录
- [ ] local 模式 → 修改密码面板不出现
- [ ] 用户看板改为卡片/行式布局，显示用户总数，管理员有标识
