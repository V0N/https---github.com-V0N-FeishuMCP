# 飞书考勤查询机器人 开发计划

> 基于 `lark-attendance-service-spec.md` 制定，技术栈：Python 3.11 + FastAPI + httpx + Docker

---

## 总体原则

- 每个步骤完成后运行对应单元测试，全部通过才进入下一步
- 测试框架：`pytest` + `pytest-asyncio`，Mock 外部飞书 API 调用（使用 `unittest.mock` / `respx`）
- 代码目录结构：
  ```
  /
  ├── app/
  │   ├── api/          # FastAPI 路由
  │   ├── service/      # 业务逻辑
  │   ├── utils/        # 工具类
  │   └── config/       # 配置加载
  ├── tests/            # 单元测试
  ├── requirements.txt
  ├── Dockerfile
  ├── docker-compose.yml
  └── README.md
  ```
- 测试命令：`pytest tests/ -v`

---

## Step 1：项目骨架 + 配置加载

### 实现内容

1. 初始化项目目录结构（`app/api/`、`app/service/`、`app/utils/`、`app/config/`、`tests/`）
2. 创建 `requirements.txt`，包含所有依赖：
   - `fastapi`、`uvicorn[standard]`、`httpx`、`python-dotenv`、`pycryptodome`、`apscheduler`、`openpyxl`
   - 测试依赖：`pytest`、`pytest-asyncio`、`respx`、`httpx`
3. 创建 `app/config/settings.py`：
   - 使用 `python-dotenv` 加载 `.env`
   - 必填项：`FEISHU_APP_ID`、`FEISHU_APP_SECRET`、`FEISHU_ENCRYPT_KEY`、`FEISHU_ADMIN_USER_ID`
   - 选填项：`FEISHU_VERIFICATION_TOKEN`、`ALLOWED_USER_IDS`（默认空）、`LOG_LEVEL`（默认 INFO）、`PORT`（默认 8000）
   - `ALLOWED_USER_IDS` 解析为 `set[str]`
4. 创建 `app/main.py`：FastAPI app 实例，注册路由，配置日志
5. 创建 `.env.example` 示例文件

### 单元测试（`tests/test_config.py`）

- 验证所有必填配置项缺失时抛出明确错误
- 验证 `ALLOWED_USER_IDS` 正确解析为 set（逗号分隔 → `{"ou_xxx1", "ou_xxx2"}`）
- 验证 `PORT` 默认值为 8000

### 验收标准

```bash
pytest tests/test_config.py -v  # 全部通过
```

---

## Step 2：飞书加密解密工具

### 实现内容

创建 `app/utils/crypto.py`：
- `decrypt_feishu_event(encrypt_str: str, encrypt_key: str) -> dict`
  - AES-256-CBC 解密
  - key = `SHA256(encrypt_key)` 的前 32 字节
  - 密文 Base64 解码，前 16 字节为 IV，剩余为密文体
  - 解密后去除 PKCS7 padding，JSON 解析返回 dict
- 异常处理：解密失败抛出 `DecryptError`

### 单元测试（`tests/test_crypto.py`）

- 用已知 encrypt_key + 明文构造加密密文，验证解密结果正确
- 验证错误的 encrypt_key 抛出 `DecryptError`
- 验证非法 Base64 字符串抛出 `DecryptError`

### 验收标准

```bash
pytest tests/test_crypto.py -v
```

---

## Step 3：飞书 API 基础客户端（Token 管理）

### 实现内容

创建 `app/utils/feishu_client.py`：
- `FeishuClient` 类（异步，基于 `httpx.AsyncClient`）
- `get_tenant_access_token() -> str`：
  - 调用 `POST https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal`
  - 本地缓存 token，距过期 10 分钟时自动刷新
  - 线程安全（asyncio.Lock）
- `request(method, path, **kwargs)` 通用请求方法：
  - 自动附加 `Authorization: Bearer {token}` 请求头
  - 非 0 code 抛出 `FeishuAPIError(code, msg)`
- `FEISHU_BASE_URL = "https://open.feishu.cn/open-apis"`

### 单元测试（`tests/test_feishu_client.py`）

使用 `respx` mock HTTP 请求：
- 验证首次调用获取 token 并缓存
- 验证 token 未过期时复用缓存（只调用一次 token 接口）
- 验证距过期 10 分钟内自动触发刷新
- 验证飞书返回 code!=0 时抛出 `FeishuAPIError`
- 验证 `request()` 自动携带 Authorization 头

### 验收标准

```bash
pytest tests/test_feishu_client.py -v
```

---

## Step 4：飞书事件回调接口（Webhook）

### 实现内容

创建 `app/api/webhook.py`：
- `POST /webhook/lark/event` 路由
- 接收请求体，调用 `decrypt_feishu_event()` 解密
- URL 验证请求（含 `challenge` 字段）：直接返回 `{"challenge": "..."}`
- 消息事件：立即返回 `200 OK`，通过 `BackgroundTasks` 异步处理
- `process_message_event(event_data: dict)` 异步处理函数（此步骤仅打日志，业务逻辑后续步骤填充）
- 解密失败返回 `400`

### 单元测试（`tests/test_webhook.py`）

使用 `httpx.AsyncClient` + FastAPI `TestClient`：
- 验证 URL 验证请求正确返回 challenge
- 验证正常消息事件返回 200（不等待异步处理）
- 验证解密失败返回 400
- 验证事件类型不是消息时不触发处理（忽略）

### 验收标准

```bash
pytest tests/test_webhook.py -v
```

---

## Step 5：时间范围解析工具

### 实现内容

创建 `app/utils/time_parser.py`：
- `parse_time_range(text: str) -> list[tuple[int, int]]`
  - 返回 `[(start_date, end_date), ...]` 列表（YYYYMMDD 整数格式）
  - 月度查询返回 1 个元组；季度查询返回 3 个元组（按月拆分）
- 支持格式：
  - `上个月` / `上月` → 上个自然月
  - `上个季度` / `上季度` → 上个自然季度（按月拆成3个区间）
  - `3月` → 当年3月
  - `2026年3月` / `2026-03` → 指定年月
  - `Q1` → 当年第一季度（1-3月，拆成3个区间）
  - `2026Q1` → 指定年份第一季度
  - 无法识别时返回上个月（默认）
- `format_time_range_label(ranges: list[tuple[int, int]]) -> str`
  - 将时间区间格式化为可读标签，如 `"2026年3月"` 或 `"2026年Q1（1-3月）"`

### 单元测试（`tests/test_time_parser.py`）

覆盖所有格式（以 2026-04-30 为当前日期）：
- `上月` → `[(20260301, 20260331)]`
- `上季度` → `[(20260101, 20260131), (20260201, 20260228), (20260301, 20260331)]`
- `3月` → `[(20260301, 20260331)]`
- `2026年3月` → `[(20260301, 20260331)]`
- `2026-03` → `[(20260301, 20260331)]`
- `Q1` → 3个区间
- `2026Q1` → 3个区间
- `Q2` → 4/5/6月各一个区间
- 无法识别的输入 → 默认上月

### 验收标准

```bash
pytest tests/test_time_parser.py -v
```

---

## Step 6：指令解析工具

### 实现内容

创建 `app/utils/command_parser.py`：
- `ParsedCommand` dataclass：`type`（query_one/query_self/query_batch/select/export/unknown）、`names`（list）、`time_text`（str）
- `parse_command(text: str) -> ParsedCommand`
  - `查 [姓名] [时间范围]` → `type=query_one`
  - `查我 [时间范围]` → `type=query_self`
  - `批量查 [姓名1,姓名2,...] [时间范围]` → `type=query_batch`，names 为列表
  - 纯数字（1-9）→ `type=select`，names=[数字字符串]
  - `导出` → `type=export`
  - 其他 → `type=unknown`
- 时间范围部分可选，缺失时 `time_text` 为空字符串（后续解析默认上月）

### 单元测试（`tests/test_command_parser.py`）

- `"查 张三 上月"` → query_one, names=["张三"], time_text="上月"
- `"查 李四"` → query_one, names=["李四"], time_text=""
- `"查我 Q1"` → query_self, time_text="Q1"
- `"批量查 张三,李四,王五 3月"` → query_batch, names=["张三","李四","王五"]
- `"1"` / `"2"` → select
- `"导出"` → export
- `"你好"` → unknown
- 姓名含空格边界情况

### 验收标准

```bash
pytest tests/test_command_parser.py -v
```

---

## Step 7：通讯录同步服务

### 实现内容

创建 `app/service/directory_service.py`：
- `DirectoryService` 类，持有内存字典：
  - `_by_name: dict[str, list[UserInfo]]`
  - `_by_open_id: dict[str, UserInfo]`
  - `_by_user_id: dict[str, UserInfo]`
- `UserInfo` dataclass：`user_id`、`open_id`、`name`、`employee_no`、`department_ids`
- `sync_all()` 异步方法：
  1. 调用 `GET /contact/v3/departments/children?department_id=0&fetch_child=true` 分页获取所有部门 ID（含根部门 "0"）
  2. 对每个部门 ID 调用 `find_by_department` 分页拉取用户
  3. 以 `user_id` 去重后更新内存字典
  4. 记录 INFO 日志（同步耗时、同步员工总数）
- `find_by_name(name: str) -> list[UserInfo]`
- `find_by_open_id(open_id: str) -> UserInfo | None`
- `find_by_user_id(user_id: str) -> UserInfo | None`

在 `app/main.py` 中：
- 应用启动时调用一次 `sync_all()`
- 使用 `apscheduler` 每小时执行一次 `sync_all()`

### 单元测试（`tests/test_directory_service.py`）

Mock `FeishuClient.request`：
- 验证分页拉取逻辑（`has_more=true` 时继续翻页，直到 `has_more=false`）
- 验证多层部门（根部门 + 2个子部门）时每个部门都被查询
- 验证 `user_id` 去重（同一人在多个部门只保留一条）
- 验证 `find_by_name` 同名返回多个、不同名返回一个
- 验证 `find_by_open_id` / `find_by_user_id` 正确查找

### 验收标准

```bash
pytest tests/test_directory_service.py -v
```

---

## Step 8：考勤统计服务

### 实现内容

创建 `app/service/attendance_service.py`：
- `AttendanceService` 类
- `_field_map: dict[str, str]`（code → title 映射，启动时初始化）
- `_target_field_codes: list[str]`（需要订阅的字段 code 列表）

**初始化方法 `initialize()`**（服务启动时自动调用）：
1. 调用 `GET /attendance/v1/user_stats_fields/query` 获取字段列表，构建 `_field_map`
2. 从 `_field_map` 中按标题名匹配找到目标字段 code（应出勤天数、实际出勤天数、迟到次数、迟到时长、早退次数、上班缺卡次数、下班缺卡次数、旷工天数、加班总时长）
3. 调用 `POST /attendance/v1/user_stats_views/update` 更新统计设置（订阅目标字段）
4. 失败时记录 ERROR，不中断启动

**查询方法 `query_stats(user_ids: list[str], time_ranges: list[tuple[int, int]]) -> dict[str, AttendanceResult]`**：
- 自动将 `user_ids` 按每批 20 人拆分
- 对每个时间区间分别调用 `POST /attendance/v1/user_stats_datas/query`
- 多个时间区间结果按字段求和合并（用于季度查询）
- 返回 `{user_id: AttendanceResult}` 字典

- `AttendanceResult` dataclass：`name`、`user_id`、各统计字段值（出勤天数、迟到次数等）、`raw_datas`

### 单元测试（`tests/test_attendance_service.py`）

Mock `FeishuClient.request`：
- 验证初始化正确构建 `_field_map`
- 验证初始化失败时不抛出异常（记录日志继续）
- 验证 21 个 user_id 被正确拆成 2 批（20+1）
- 验证季度查询（3个时间区间）结果按字段求和合并
- 验证无考勤数据时返回空 dict

### 验收标准

```bash
pytest tests/test_attendance_service.py -v
```

---

## Step 9：消息发送服务 + 卡片构建

### 实现内容

创建 `app/service/message_service.py`：
- `send_text(open_id: str, text: str)` 发送纯文本消息
- `send_card(open_id: str, card: dict)` 发送卡片消息（`msg_type=interactive`）

创建 `app/utils/card_builder.py`：
- `build_attendance_card(user_info: UserInfo, time_label: str, result: AttendanceResult) -> dict`
  - 构建 spec 3.4.2 格式的考勤结果卡片
  - 异常字段（`Abnormal=true`）前加 ⚠️ 标记
  - 时长字段（分钟）自动换算为小时分钟格式
- `build_ambiguous_card(candidates: list[UserInfo]) -> dict`
  - 构建 spec 3.4.3 格式的同名选择卡片
  - 最多展示前 10 个候选人
- `build_error_text(scenario: str, **kwargs) -> str`
  - 根据 spec 9 错误提示规范返回对应错误文案

### 单元测试（`tests/test_card_builder.py`）

- 验证 `build_attendance_card` 包含姓名、时间范围、各考勤字段
- 验证异常字段（Abnormal=true）显示 ⚠️ 标记
- 验证时长字段分钟转换（90分钟 → "1小时30分钟"）
- 验证 `build_ambiguous_card` 包含所有候选人信息
- 验证 `build_error_text` 各场景文案正确

### 验收标准

```bash
pytest tests/test_card_builder.py -v
```

---

## Step 10：会话状态管理

### 实现内容

创建 `app/service/session_service.py`：
- `SessionService` 单例
- `set_pending_selection(open_id: str, candidates: list[UserInfo], query_params: dict)`
  - 存入内存，TTL 5 分钟
- `get_pending_selection(open_id: str) -> dict | None`
  - 返回 `{candidates, query_params}` 或 None（已过期/不存在）
- `clear_pending_selection(open_id: str)`
- `set_export_context(open_id: str, results: list[AttendanceResult])`，TTL 10 分钟
- `get_export_context(open_id: str) -> list[AttendanceResult] | None`
- TTL 用时间戳实现（不依赖外部库）

### 单元测试（`tests/test_session_service.py`）

- 验证 set/get 正常工作
- 验证 5 分钟后 `get_pending_selection` 返回 None（mock time）
- 验证 10 分钟后 `get_export_context` 返回 None
- 验证 `clear_pending_selection` 后立即返回 None

### 验收标准

```bash
pytest tests/test_session_service.py -v
```

---

## Step 11：权限校验工具

### 实现内容

创建 `app/utils/permission.py`：
- `is_allowed(open_id: str) -> bool`
  - 读取 settings.ALLOWED_USER_IDS，判断是否在白名单中
- `check_query_permission(requester_open_id: str, target_open_ids: list[str]) -> bool`
  - 若查询目标包含非本人（open_id 不等于 requester），则要求 requester 在白名单中

### 单元测试（`tests/test_permission.py`）

- 白名单用户查询他人 → True
- 非白名单用户查询他人 → False
- 任何用户查询自己 → True
- 白名单为空时，查询他人 → False

### 验收标准

```bash
pytest tests/test_permission.py -v
```

---

## Step 12：核心业务逻辑编排（消息处理器）

### 实现内容

创建 `app/service/message_handler.py`：
- `handle_message(event_data: dict)` 异步入口
  - 提取 `sender.open_id`、消息文本内容
  - 记录 INFO 审计日志（查询人 open_id、消息内容、时间戳）
  - 按 spec 4.1 指令解析优先级处理：
    1. 检查是否有待确认的同名选择状态
    2. 若有且消息为纯数字 → 执行选择逻辑
    3. 若有但消息非数字 → 清除状态，走正常指令解析
    4. 正常指令解析

- `handle_query_one(open_id, name, time_text)` 单人查询：
  1. 权限校验（查他人需白名单）
  2. 内存查找用户（`find_by_name`）
  3. 未找到 → 发送错误消息
  4. 找到多个 → 存 session，发送同名选择卡片
  5. 找到唯一 → 查询考勤，发送结果卡片

- `handle_query_self(open_id, time_text)` 查我：
  1. 从缓存查 open_id 对应 user_id（或调用 API 获取）
  2. 查询考勤，发送结果卡片

- `handle_query_batch(open_id, names, time_text)` 批量查询：
  1. 权限校验
  2. 逐个 name 查用户（同名的取第一个，并附加说明）
  3. 批量查询考勤（自动分批）
  4. 逐张发送单人卡片

- `handle_selection(open_id, index_str)` 选择处理：
  1. 取 session 候选列表
  2. 验证序号合法性
  3. 执行查询

### 单元测试（`tests/test_message_handler.py`）

Mock `DirectoryService`、`AttendanceService`、`MessageService`、`SessionService`、`PermissionChecker`：
- 验证单人查询完整流程（找到唯一用户 → 发卡片）
- 验证同名用户流程（找到多个 → 发选择卡片 → 回复1 → 查询结果）
- 验证"查我"流程（open_id → user_id → 查询）
- 验证批量查询（2人，各发1张卡片）
- 验证权限拦截（非白名单查他人 → 发错误消息）
- 验证未找到用户 → 发错误消息
- 验证指令解析优先级（有待选状态时输入"1"走选择逻辑）

### 验收标准

```bash
pytest tests/test_message_handler.py -v
```

---

## Step 13：日志审计

### 实现内容

在 `app/utils/audit_logger.py` 中：
- `AuditLogger` 工具类，日志格式为 JSON 结构化日志
- `log_query(requester_open_id, requester_name, target_names, time_range, result_status)`
  - result_status：success / not_found / no_permission / api_error
- 使用 Python 标准 `logging` 模块，配置 `LOG_LEVEL` 环境变量

在 `app/main.py` 中统一配置日志（JSON 格式输出到 stdout）。

### 单元测试（`tests/test_audit_logger.py`）

- 验证日志输出包含必要字段（open_id、target、time_range、status、timestamp）
- 验证 result_status 各值正确记录

### 验收标准

```bash
pytest tests/test_audit_logger.py -v
```

---

## Step 14：集成测试

### 实现内容

创建 `tests/test_integration.py`：
- 使用 FastAPI `TestClient` + `respx` mock 所有飞书 API
- 模拟完整场景的 HTTP 请求链路

### 集成测试场景

1. **单人查询完整链路**：
   - POST `/webhook/lark/event`（加密事件：`查 张三 上月`）
   - Mock: 通讯录已有张三（唯一）、考勤 API 返回数据
   - 期望：调用消息 API 发送卡片，返回 200

2. **同名用户选择链路**：
   - 第一条消息：`查 张三 上月`
   - Mock: 通讯录找到两个张三
   - 期望：发送选择卡片，session 存入状态
   - 第二条消息：`1`
   - 期望：查询考勤，发送结果卡片

3. **查我链路**：
   - 消息：`查我 上月`，sender.open_id = `ou_test`
   - Mock: 通讯录缓存中有该 open_id
   - 期望：正确查询考勤并返回卡片

4. **批量查询链路**：
   - 消息：`批量查 张三,李四 3月`
   - 期望：发送 2 张卡片

5. **无权限拦截**：
   - 非白名单用户查他人
   - 期望：发送权限错误消息

6. **URL 验证**：
   - POST 包含 `challenge` 字段
   - 期望：返回 `{"challenge": "xxx"}`

### 验收标准

```bash
pytest tests/test_integration.py -v
```

---

## Step 15：Docker 部署配置

### 实现内容

1. `Dockerfile`：
   - 基于 `python:3.11-slim`
   - 复制 `requirements.txt`，`pip install`
   - 复制应用代码
   - `CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]`

2. `docker-compose.yml`：
   - 服务名：`feishu-attendance-bot`
   - 端口映射：`${PORT:-8000}:8000`
   - 重启策略：`unless-stopped`
   - `env_file: .env`
   - 健康检查：`GET /health`（需在 main.py 中添加 `/health` 路由）

3. `.dockerignore`：排除 `tests/`、`.env`、`__pycache__`

4. `README.md`：
   - 飞书后台配置步骤（应用创建、权限申请、通讯录权限范围配置、事件订阅、Encrypt Key 开启）
   - 环境变量说明（含获取 `FEISHU_ADMIN_USER_ID` 的方法）
   - Docker 部署步骤

### 验收标准

```bash
docker build -t feishu-attendance-bot .  # 构建成功，无报错
```

---

## Step 16：P1 功能 - Excel 导出（可选）

### 实现内容

创建 `app/service/export_service.py`：
- `generate_excel(results: list[AttendanceResult], time_label: str) -> bytes`
  - 使用 `openpyxl` 生成 Excel
  - 列：姓名、工号、部门、时间范围、各考勤字段
  - 返回文件字节流

在 `message_handler.py` 中增加 `handle_export(open_id)` 处理器：
- 取 session 中的 `export_context`
- 调用 `generate_excel`
- 通过飞书文件上传接口上传，再以 file 消息发送

### 单元测试（`tests/test_export_service.py`）

- 验证生成的 Excel 包含正确表头和数据行
- 验证空数据时生成合法的空表格

### 验收标准

```bash
pytest tests/test_export_service.py -v
```

---

## 完整测试通过标准

所有步骤完成后，运行全量测试：

```bash
pytest tests/ -v --tb=short
```

**目标：全部 pass，0 failure，覆盖率 ≥ 80%**

```bash
pytest tests/ --cov=app --cov-report=term-missing
```

---

## 依赖步骤关系图

```
Step 1 (项目骨架)
    └── Step 2 (加密解密)
    └── Step 3 (飞书客户端)
            ├── Step 4 (Webhook 接口)
            ├── Step 7 (通讯录同步)
            └── Step 8 (考勤服务)
Step 5 (时间解析)  ─────────────────────┐
Step 6 (指令解析)  ─────────────────────┤
Step 9 (消息发送 + 卡片)  ───────────────┤
Step 10 (会话状态)  ─────────────────────┤
Step 11 (权限校验)  ─────────────────────┼──→ Step 12 (业务编排)
Step 13 (审计日志)  ─────────────────────┘
                                              └── Step 14 (集成测试)
                                                      └── Step 15 (Docker)
                                                              └── Step 16 (P1导出, 可选)
```
