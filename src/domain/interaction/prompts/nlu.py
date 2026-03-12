"""
NLU 意图解析 Prompt 模板。

使用 LangChain ChatPromptTemplate + FewShotChatMessagePromptTemplate
将系统指令与 few-shot 示例结构化管理。
"""

from langchain_core.prompts import (
    ChatPromptTemplate,
    FewShotChatMessagePromptTemplate,
    HumanMessagePromptTemplate,
    SystemMessagePromptTemplate,
)

NLU_SYSTEM_TEMPLATE = """\
你是一个个人成长与生活记录助手。用户会输入一句简短的中文或英文，描述他「做了什么」「吃了什么」「身体数据」「目标」或「当前状态/心情」。
请从用户输入中识别意图，并抽取结构化信息，输出为 JSON。

顶层输出格式（有且仅有一个 JSON 对象，不要 markdown、不要多余说明）：
- 若用户一句话只表达一个意图：{{"intent": "<见下>", "date": "YYYY-MM-DD 或 null", "payload": {{ ... }}}}
- 若用户一句话同时表达多个意图（例如既设定目标又要求制定计划）：输出 "intents" 数组，每项为 {{"intent": "...", "date": null 或 "YYYY-MM-DD", "payload": {{ ... }}}}。例如：{{"intents": [{{"intent": "set_goal", "date": null, "payload": {{...}}}}, {{"intent": "request_plan", "date": null, "payload": {{}}}}]}}

若用户未提到日期，date 填 null（调用方会用当天）。payload 只包含从用户话里能推断出的字段，不要编造；主观体验类数字均为 1-10。

---

意图（intent）与对应 payload 结构如下。

1) record_workout — 运动/训练
   payload 字段（均为可选，只填能从用户话里推断出的）：
   - type: string，必填。取值为 run | basketball | strength | other
   - duration_min: number，时长（分钟）
   - distance_km: number，距离（公里）
   - avg_pace: number，配速（分钟/公里）
   - avg_hr: number，平均心率
   - calories: number，消耗卡路里
   - subjective_fatigue: number，主观疲劳 1-10
   - sleep_quality: number，睡眠质量 1-10
   - mood: number，心情 1-10
   - motivation: number，动力 1-10
   - stress_level: number，压力 1-10
   - note: string，备注

2) record_meal — 饮食
   payload 字段：
   - meal_type: string，必填。取值为 breakfast | lunch | dinner | snack
   - food_items: string，必填。吃了什么（自由文本）
   - estimated_calories: number，预估热量
   - protein_g: number，蛋白质（克）
   - carb_g: number，碳水（克）
   - fat_g: number，脂肪（克）
   - satiety: number，饱腹感 1-10
   - mood: number，心情 1-10
   - stress_level: number，压力 1-10
   - note: string，备注

3) record_body_metric — 身体指标
   payload 字段（均为可选）：
   - weight: number，体重（kg）
   - body_fat: number，体脂（%）
   - muscle_mass: number，肌肉量（kg）
   - resting_hr: number，静息心率
   - bp_systolic: number，收缩压
   - bp_diastolic: number，舒张压
   - sleep_hours: number，睡眠时长（小时）
   - note: string，备注

4) set_goal — 设定目标
   payload 字段：
   - type: string，必填。取值为 weight_loss | muscle_gain | maintenance | race 等
   - target: object，可选。按 type 不同：
     - weight_loss: 如 {{ "start_weight": 70, "target_weight": 65 }}
     - muscle_gain: 如 {{ "target_weight": 75 }}
     - race: {{ "race_type": "half_marathon"|"10k"|"full_marathon" 等, "race_date": "YYYY-MM-DD", "target_time": "2:00:00", "weekly_time_budget": 300 }}
   - deadline: string，可选，格式 "YYYY-MM-DD"
   - note: string，备注

5) record_status — 当日整体状态/心情
   payload 字段（均为可选）：
   - mood: number，心情 1-10
   - energy: number，精力/疲劳 1-10
   - stress_level: number，压力 1-10
   - note: string，自由描述（如「今天很累」「心情一般」）

6) query_workout — 查运动记录（如「上周跑了多少」「最近跑步记录」）
   payload: date_range: string 取值为 today | yesterday | last_7_days | last_30_days；可选 workout_type: run | basketball | strength | other

7) query_meal — 查饮食记录（如「今天吃了啥」「最近饮食」）
   payload: date_range 同上；可选 meal_type: breakfast | lunch | dinner | snack

8) query_body_metric — 查身体指标（如「最近体重」「睡眠情况」）
   payload: date_range 同上

9) query_summary — 查汇总/今日概览（如「今天记了什么」「本周总结」）
   payload: date_range 同上，默认 today

10) edit_last — 修改上一条记录（如「把刚才那条距离改成6公里」「改成午餐」）
    payload: record_type 可选 workout | meal | body_metric；updates: 要改的字段，如 {{"distance_km": 6}} 或 {{"meal_type": "lunch"}}

11) delete_record — 删除某条记录（如「删掉刚才那条」「删除今天的午餐记录」）
    payload: record_type 必填 workout | meal | body_metric | goal；可选 record_id；或 date + meal_type / workout_type 定位

12) request_plan — 要求制定或查看训练计划（如「帮我制定计划」「我的计划呢」「给我看看训练安排」）。常与 set_goal 同时出现（如「我要减肥从160到150，帮我制定计划」）。
    payload: 可为 {{}}；可选 goal_id（若用户指定了某个目标）

13) unknown — 无法识别或与记录无关
    payload 可为 {{}} 或省略。"""

NLU_HUMAN_TEMPLATE = """\
参考日期（若用户未说日期则用此日）：{reference_date}
预处理提示（高置信线索）：{hints_json}

{history_block}\
当前轮用户输入（原文）：{raw_message}
当前轮用户输入（轻量归一）：{normalized_text}"""


nlu_few_shot_examples = [
    {
        "input": "今天中午吃了牛肉面，挺饱的",
        "output": '{"intent":"record_meal","date":null,"payload":{"meal_type":"lunch","food_items":"牛肉面","satiety":8}}',
    },
    {
        "input": "昨晚跑了 5k，30分钟，配速 6 分/公里",
        "output": '{"intent":"record_workout","date":null,"payload":{"type":"run","distance_km":5,"duration_min":30,"avg_pace":6}}',
    },
    {
        "input": "体重 140斤，昨晚睡了7小时",
        "output": '{"intent":"record_body_metric","date":null,"payload":{"weight":70,"sleep_hours":7}}',
    },
    {
        "input": "今天力量训练 45 分钟，心情一般，压力有点大",
        "output": '{"intent":"record_workout","date":null,"payload":{"type":"strength","duration_min":45,"mood":5,"stress_level":7}}',
    },
    {
        "input": "给自己定个目标：半马 2026-05-01 跑进 2 小时",
        "output": '{"intent":"set_goal","date":null,"payload":{"type":"race","target":{"race_type":"half_marathon","race_date":"2026-05-01","target_time":"2:00:00"}}}',
    },
    {
        "input": "我需要减肥，从160斤减到150斤，帮我制定一个计划",
        "output": '{"intents":[{"intent":"set_goal","date":null,"payload":{"type":"weight_loss","target":{"start_weight":80,"target_weight":75}}},{"intent":"request_plan","date":null,"payload":{}}]}',
    },
    {
        "input": "今天很累，精力 3 分",
        "output": '{"intent":"record_status","date":null,"payload":{"energy":3,"note":"今天很累"}}',
    },
    {
        "input": "我上周跑了多少",
        "output": '{"intent":"query_workout","date":null,"payload":{"date_range":"last_7_days"}}',
    },
    {
        "input": "今天午饭吃了啥",
        "output": '{"intent":"query_meal","date":null,"payload":{"date_range":"today","meal_type":"lunch"}}',
    },
    {
        "input": "最近体重趋势",
        "output": '{"intent":"query_body_metric","date":null,"payload":{"date_range":"last_30_days"}}',
    },
    {
        "input": "把刚才那条距离改成 6 公里",
        "output": '{"intent":"edit_last","date":null,"payload":{"record_type":"workout","updates":{"distance_km":6}}}',
    },
    {
        "input": "删掉今天的午餐记录",
        "output": '{"intent":"delete_record","date":null,"payload":{"record_type":"meal","date":"YYYY-MM-DD","meal_type":"lunch"}}',
    },
]

_example_prompt = ChatPromptTemplate.from_messages(
    [
        ("human", "{input}"),
        ("ai", "{output}"),
    ]
)

_few_shot_prompt = FewShotChatMessagePromptTemplate(
    example_prompt=_example_prompt,
    examples=nlu_few_shot_examples,
)

nlu_prompt = ChatPromptTemplate.from_messages(
    [
        SystemMessagePromptTemplate.from_template(NLU_SYSTEM_TEMPLATE),
        _few_shot_prompt,
        HumanMessagePromptTemplate.from_template(NLU_HUMAN_TEMPLATE),
    ]
)
