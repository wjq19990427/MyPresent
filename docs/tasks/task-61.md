# task-61 · 数据库结构清理与分类体系统一

## 变更说明

**类型**：重构  
将数据库中遗留的旧标签系统彻底移除，统一目标/待办/事务三类实体的分类体系至同一张表，并清理若干冗余字段，为后续前后端重构打下干净的数据地基。用户体验上，待办和事务的分类选项将与年度目标完全打通，分类管理只需在一处操作。

---

## 涉及文件

- `core/db_manager.py`
- `core/constants.py`
- `components/tab_planning.py`
- `components/cards.py`
- `components/tab_upload.py`

---

## 变更清单

### 1. 删除旧标签系统

- `session_tags` 表废弃（数据可丢弃，`sessions.topics` 已是新标准）
- `tags_registry` 表废弃
- 启动时不再创建这两张表；存量库执行 DROP TABLE 迁移

### 2. 删除冗余字段

- `calendar_todos.status` 字段删除，`todo_state`（todo/done/moved）是唯一状态来源
- `sessions.is_complete` 字段删除，"必填项是否齐全"改为业务层实时计算，不再持久化

### 3. 统一分类体系

- `goal_categories` 表重命名为 `categories`
- 新增 `applicable_to` 字段，取值：`goal` / `todo` / `activity` / `all`，标记该分类适用范围
- 系统默认分类（`is_system=1`，不可删）：身心健康 / 亲密关系 / 事业发展 / 个人成长 / 杂项（新增）
- `calendar_todos.category` 改为 FK → `categories.name`，不可为空
- `daily_activities.category` 改为 FK → `categories.name`，不可为空
- 代码中的 `TODO_CATEGORIES` 常量废弃，UI 改为从 `categories` 表动态读取

### 4. feeling / emotion_note 语义固化

无 schema 变更，仅明确语义边界并在代码注释和 UI 文案中统一：
- `feeling`：用户手写的第一感受，主动填写，自由文本
- `emotion_note`：AI 生成的情绪解读，只读展示，由 AI 分析写入，用户不直接编辑

---

## 数据迁移约束

- 存量 `calendar_todos.category` 和 `daily_activities.category` 中若有不在新 `categories` 表的值，迁移时自动归入「杂项」
- 存量 `annual_goals.category` 同理，不在表中的值迁移时归入「杂项」
- `session_tags` 数据直接丢弃（`sessions.topics` 已是权威来源）
- 所有迁移在 `init_db()` / `migrate()` 启动时幂等执行

---

## 验收标准

- 待办新建/编辑时，分类下拉来自 `categories` 表，与年度目标分类列表完全一致
- 事务新建/编辑时，分类下拉同上
- 用户在系统设置中增删自定义分类，三处（目标/待办/事务）同步生效
- 待办关联年度目标时，分类自动预填为该目标的分类
- 待办完成转事务时，分类自动继承
- 存量数据迁移后无丢失，原有记录分类字段有值（最差归入「杂项」）
- `session_tags`、`tags_registry` 表不再存在于数据库中
