## 总体架构与技术实现

整体分为 4 层 + 1 条时间轴：

1. **数据层（事实记录）**
2. **知识与记忆层（规则 + 长期记忆）**
3. **决策与规划层（agent 大脑）**
4. **交互层（我和 agent 怎么对话）**
5. **时间维度（每天/每周/每阶段循环）**

### 1. 数据层（事实记录）

使用 MySQL 存储结构化数据，Redis 做缓存，Milvus/ES 做长期记忆检索。

- **训练记录 `workouts`**
  - 字段示例：
    - `id`, `date`, `type`（run / basketball / strength / other）
    - `duration_min`, `distance_km`, `avg_pace`, `avg_hr`, `calories`
    - 主观体验（一等公民）：`subjective_fatigue`（1–10）, `sleep_quality`（1–10）, `mood`, `motivation`, `stress_level`
    - `note`

- **身体指标 `body_metrics`**
  - 字段示例：
    - `id`, `date`
    - `weight`, `body_fat`, `muscle_mass`
    - `resting_hr`, `bp_systolic`, `bp_diastolic`
    - `sleep_hours`

- **饮食记录 `meals`**
  - 起步阶段可以简化为：
    - `id`, `date`, `meal_type`（breakfast / lunch / dinner / snack）
    - `food_items`（自由文本）
    - `estimated_calories`, `protein_g`, `carb_g`, `fat_g`（可选）
    - 主观体验：`satiety`（1–10）, `mood`（1–10）, `stress_level`（可选）

- **个人配置与偏好 `user_profile`**
  - 静态/低频数据：
    - `height`, `gender`, `birth_year`
    - `activity_level`（sedentary / moderate / high）
    - 饮食偏好与忌口（是否吃辣、牛奶、牛肉、猪肉等）

- **目标系统 `goals`**
  - 所有目标（减脂、增肌、维持、半马等）统一用一个 Goal 模型表示，只是类型和 `target` 结构不同。
  - 通用字段：
    - `id`
    - `type`：`weight_loss` / `muscle_gain` / `maintenance` / `race` / ...
    - `target`：按类型不同存结构化目标内容（见下）
    - `deadline`：目标截止日期（例如今天 + 3 个月 / 6 个月）
    - `status`：`planning` / `ongoing` / `completed` / `abandoned`
    - `created_at`, `updated_at`, `note`
  - 减脂目标示例（weight_loss）：
    - `type = weight_loss`
    - `target = { start_weight, target_weight, expected_loss }`
    - 例如：「6 个月瘦 10 斤」→ `start_weight = 72kg, target_weight = 67kg, expected_loss = 5kg`
  - 比赛型目标示例（race）：
    - `type = race`
    - `target = { race_type, target_time, weekly_time_budget, constraints }`
    - `race_type`（`half_marathon` / `10k` / `full_marathon` 等）
    - `race_date`
    - `target_time`（如 1:45:00，可选）
    - `weekly_time_budget`（每周可训练小时数）
    - `constraints`（伤病、工作限制、场地限制等）
  - 支持同时存在多个 active goals（例如「3 个月挑战半马」+「6 个月瘦 10 斤」），由上层规划模块综合考虑。
  - **目标轨迹（Trajectory）**：例如减脂目标不只是「6 个月瘦 5kg」一个点，而是规划一条合理体重变化曲线（前期稍快、中期稳定、后期保守）；每周复盘时对比「实际曲线 vs 目标曲线」，偏差大时再判断是饮食、活动量还是压力睡眠问题，做针对性调整。
  - **目标层级与策略切换**：当多个目标冲突时（如备赛后期 vs 减脂），系统有显式规则——例如比赛前 4 周性能优先、比赛后 2–4 周恢复与体重并重——实现策略切换，而不是一条线撸到底。

### 主观体验最主要的

**把主观体验当作一等特征**：真正想要的是长期可持续的高质量生活方式，可持续性的核心变量是——你觉得这件事痛不痛苦、累不累、烦不烦、有没有成就感。

- **数据层**：除客观指标外，刻意记录：
  - `subjective_fatigue`（训练后/次日）
  - `mood`（整体心情）
  - `motivation`（对训练/饮食的意愿）
  - `stress_level`（工作/生活压力）
- **记忆与规划**：Memory Writer 总结时，不只写「这周跑了 40km、体重降 0.3kg」，也写「这周训练+饮食较严，主观上非常疲惫、社交受影响，下次不要把这种组合连续超过 2 周」。规划时，对历史上让你主观体验很差的训练+饮食模式，自动降低使用频率或限制连续使用时间。

### 2. 知识与记忆层

分为「通用知识」和「个体化记忆」两部分。

- **通用知识（规则/公式）**
  - BMR / TDEE 估算公式。
  - 减脂 / 维持 / 增肌 的热量区间策略。
  - 蛋白质摄入建议（g/kg 体重）。
  - 不同训练日类型（休息日 / 轻松日 / 关键课）对应的饮食策略。
  - 实现方式：
    - 一部分写成代码公式（确定和可重复）。
    - 一部分写入 LLM 的系统提示词（营养与训练原则）。

- **个体化长期记忆**
  - 用 Milvus/ES 存储「记忆卡片」，如：
    - 某一阶段的训练/饮食/体重变化总结。
    - 某些模式：如「高跑量 + 低碳水时主观状态很差」。
  - 每日/每周有一个 Memory Writer：
    - 从训练/饮食/对话中抽取摘要，生成向量嵌入，写入记忆库。
  - agent 做规划时：
    - 先基于当前话题（例如「半马备赛」「减脂」）从记忆库检索相关记忆。
    - 把这些记忆连同近期数据一起输入 LLM。
  - **失败经验的系统总结**：不只记录成功周期，也把失败周期（没完成备赛、减脂中途崩掉）总结成结构化记忆，例如「当时失败主要是因为工作强度突增 + 饮食过于激进 → 持续 2 周后崩盘」。下次遇到类似背景（如工作又开始爆炸）时，agent 会提醒你上次在类似环境下极端计划是怎么崩的，并主动给出更温和的方案。

### 3. 决策与规划层（agent 大脑）

核心有三个层级：

1. **长期与阶段性规划（目标驱动）**
   - 输入：
     - 当前 active goals（如「16 周后跑半马」+「3 个月减脂」）。
     - 最近 3–6 个月训练/身体指标数据。
   - 输出：
     - 阶段划分（基础期 / 提升期 / 峰值期 / 减量期）。
     - 每个阶段的周跑量区间、关键训练课类型比例。
     - 每个阶段的体重/体脂/宏观营养方向。

2. **周计划生成器 `WeeklyPlanner`**
   - 输入：
     - 短期目标（例如「本周是第 5/16 周，处于提升期」）。
     - 最近 2–4 周的训练数据和疲劳状态。
     - 本周日程（哪些天可训练、是否有固定打球时间等）。
   - 输出（结构化 JSON）：
     - 每天的：
       - `day_type`：`rest_day` / `easy_day` / `key_workout_day`。
       - `workout_plan`：训练类型、距离/时间、配速/强度范围等。
       - `nutrition_target`：目标热量、蛋白质/碳水/脂肪区间。
   - 周计划同时输入「训练模块」和「饮食模块」。

3. **日内即时调整 `DailyAdjuster`**
   - 输入：
     - 当天已经完成的训练和饮食记录。
     - 当前主观状态（疲劳、睡眠质量、情绪）。
   - 输出：
     - 当天剩余时间的战术级决策：
       - 晚饭吃什么方向，是否加餐。
       - 是否降低/提高明天训练强度。
     - 必要时对本周后续计划做微调（如超负荷则减量）。

> 训练与饮食强绑定：  
> `day_type` 决定当天饮食策略：  
> - 关键课日：高碳水、适中热量，优先保证训练质量和恢复。  
> - 休息日：略低热量、略低碳水，推进体重/体脂目标。  

### 4. 交互层

为单一用户（我自己）设计，从简单到复杂。

#### 4.1 自然语言理解与落表（已实现）

目标：让 agent 理解自然语言（目标、状态、做了什么、吃了什么等），并整理成结构化数据落表。

- **意图类型**（见 `src/core/interaction/schemas.py`）：
  - `record_workout`：运动/训练（跑步、打球、力量等）
  - `record_meal`：饮食（早/中/晚/加餐）
  - `record_body_metric`：身体指标（体重、体脂、睡眠等）
  - `set_goal`：设定目标（减脂、半马、维持等）
  - `record_status`：当日整体状态/心情/感受
  - `unknown`：无法识别

- **流程**：用户输入 → `parse_user_message()`（LLM 解析）→ `ParsedRecord`（意图 + 日期 + payload）→ `apply_parsed_record()` → 写入 MySQL（workouts / meals / body_metrics / goals）。

- **API**：`POST /api/record`  
  - Body：`{"message": "今天中午吃了牛肉面，挺饱的", "date": "2025-02-27"}`（`date` 可选，默认当天）  
  - 返回：解析结果（intent、date、payload）与落表结果（表名、新记录 id 或错误信息）。

- **配置**：`.env` 中需配置 `OPENAI_API_KEY`、可选 `OPENAI_MODEL`（默认 gpt-4o）。MySQL 启动时通过 `init_mysql(app)` 初始化，供落表使用。

1. **CLI / Notebook 交互（MVP）**
   - 通过命令行/Notebook 与 agent 对话：
     - 例如：「帮我看下这周计划」「今天晚上打球，晚饭吃什么」。

2. **个人 Web 控制台（后续）**
   - 页面包含：
     - 体重/体脂/周跑量等趋势图。
     - 当前阶段目标与周计划卡片。
     - 一个对话窗口与 agent 互动。

3. **提醒与推送（再后续）**
   - 通过微信/Telegram/飞书机器人等：
     - 每天早晨推送「今日计划」。
     - 每天晚上推送「今日总结 + 明天建议」。

### 半马目标示例（结构设计）

以「16 周后挑战半马」为例：

- **创建目标（自然语言 → 结构化）**
  - 对话示例：
    - 「我想在 2025 年 11 月跑一个半马，目标 1 小时 45 分钟，我现在每周大概能跑 3 次。」
  - 解析为 `goals` 表的一条记录：
    - `type = race`
    - `race_type = half_marathon`
    - `race_date = 2025-11-xx`
    - `target_time = 1:45:00`
    - `weekly_time_budget ≈ 3–4 次训练`

- **宏观周期（16 周备赛）**
  - 阶段划分：
    - 第 1–4 周：基础有氧期（建立跑量和习惯）。
    - 第 5–10 周：提升期（加入更多节奏跑和间歇）。
    - 第 11–14 周：峰值期（接近比赛配速训练）。
    - 第 15–16 周：减量期（减少跑量，保持状态）。

- **周计划结构（示例 JSON 抽象）**
  - 每周：
    - `week_index`（第几周）
    - `phase`（基础 / 提升 / 峰值 / 减量）
    - `weekly_mileage_target`（km 区间）
    - `days[]`：
      - `date`
      - `day_type`（rest_day / easy_day / key_workout_day）
      - `workout_plan`（如「轻松跑 8km @ 6:00–6:15/km」）
      - `nutrition_target`（热量 + 三大营养素范围）

这些结构会由 `RacePlanner` / `WeeklyPlanner` 等模块生成，并写入数据库，供 CLI/Web/提醒系统使用。

### 时间维度与运转方式

- **每日循环**
  - 记录当天训练、饮食、身体状态。
  - `DailyAdjuster` 根据偏差给出当天/明天的调整建议。
  - `Memory Writer` 抽取当天关键事件写入长期记忆。

- **每周循环**
  - 对本周执行情况复盘（训练达成度、体重变化、主观状态）。
  - 调整下一周的训练+饮食计划。

- **每阶段/每个目标结束后**
  - 生成更高层次总结（如「这次 16 周半马备赛的经验教训」）。
  - 存入记忆库，以便下次设定类似目标时自动参考。

