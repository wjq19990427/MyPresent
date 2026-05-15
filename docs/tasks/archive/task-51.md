# Task #51 — 管理员用户管理面板

## 变更说明

**新功能** · 管理员账户登录后，可在「⚙️ 系统」页面新增用户、查看已有用户名列表；普通用户看不到此面板，任何人均无法通过界面删除账户。

---

## 改动范围

- **修改**：`core/db_manager.py`（全局认证库节，新增两个函数）
- **修改**：`components/eval_dashboard.py`（新增管理员面板区块）
- **修改**：`docs/api/core.md`（补充上述两个函数的契约）
- **不许碰**：`users` 表 Schema、`app.py`、其他任何文件

---

## db_manager.py 新增函数

### `create_user(username: str, password: str) -> None`

- **用途**：在全局库 `users` 表创建新用户（`is_admin=0`）
- **密码算法**：与 `verify_user` 使用完全相同的 PBKDF2-SHA256（20 万次）+ 独立 salt
- **约束**：
  - `username.strip()` 为空时抛 `ValueError("用户名不能为空")`
  - 用户名已存在时抛 `ValueError("用户名已存在")`
- **副作用**：写 `config.get_global_db_path()`；仅插入 `users` 表，不创建业务库目录

### `list_usernames() -> list[str]`

- **返回**：所有已注册用户名，按字母升序排列
- **副作用**：无（只读全局库）
- **字段限制**：仅返回 `username`，不含密码、salt、is_admin 等任何其他字段

---

## components/eval_dashboard.py 行为

在现有 `render_eval_dashboard()` 的**末尾**追加管理员面板，满足以下所有条件才渲染：

1. `DEPLOY_MODE == "cloud"`
2. `get_user_is_admin(st.session_state.get("_current_user", ""))` 返回 `True`

### 面板内容

**用户列表区**：调用 `list_usernames()`，以文本方式展示所有用户名（只显示用户名，无其他信息）。

**新增用户表单**：
- 用户名输入框（文本，必填）
- 密码输入框（`type="password"`，预填默认密码 `"MyPresent@000"`，可覆盖）
- 「新增用户」确认按钮
- 成功后：清空输入框，刷新用户名列表，显示成功提示
- 失败后：`st.error` 显示 `create_user` 抛出的 `ValueError` 信息

**面板不提供**：禁用、删除、修改密码等任何账户操作入口。

---

## 验收清单

- [ ] `python -c "import app, core, skills, components"` 通过
- [ ] local 模式启动：`⚙️ 系统` 页面无任何新增内容（面板不渲染）
- [ ] cloud 模式 + 普通用户登录：`⚙️ 系统` 页面无新增内容
- [ ] cloud 模式 + 管理员登录：`⚙️ 系统` 页面底部出现用户管理面板，可见当前用户名列表
- [ ] 填写新用户名（密码留默认）→ 点新增 → 列表刷新出现新用户名
- [ ] 填写自定义密码 → 点新增 → 新用户可用该密码在登录页正常登录
- [ ] 填写已存在用户名 → 点新增 → 界面显示"用户名已存在"错误，无异常崩溃
- [ ] 用户名留空 → 点新增 → 界面显示"用户名不能为空"，无异常崩溃
- [ ] `docs/api/core.md` 已同步更新 `create_user` 和 `list_usernames` 契约
- [ ] commit 符合规范（建议 `feat(auth): 管理员用户管理面板 · 关联 #51`）
- [ ] 在 worktree 分支提交，未 push main
