# 飞书考勤查询机器人 Service Specification

## 1. 项目概述

- 目标：飞书机器人后端服务，用户在飞书聊天中发送指令即可查询员工考勤统计数据
- 技术栈：Python 3.11 + FastAPI + Uvicorn + PyJWT + python-dotenv + Docker
- 飞书版本：国内飞书（API Base URL: <https://open.feishu.cn/document/server-docs/api-call-guide/calling-process/overview>）
- 部署方式：Docker容器化部署
- 核心规则：考勤数据不落地存储，查询即返回，所有操作留审计日志

***

## 2. 功能需求（P0必须实现，P1可选实现）

### 2.1 核心功能清单

| 功能          | 描述                                                                             | 优先级 |
| ----------- | ------------------------------------------------------------------------------ | --- |
| 飞书消息事件接收    | 接收飞书机器人推送的用户消息事件，解析指令                                                          | P0  |
| 单人考勤查询      | 指令格式：`查 [姓名] [时间范围]`，返回该用户考勤统计                                                 | P0  |
| 批量考勤查询      | 指令格式：`批量查 [姓名1,姓名2,姓名3] [时间范围]`，返回多个用户的考勤汇总                                    | P0  |
| 个人考勤查询      | 用户发送`查我 [时间范围]`，自动查询自己的考勤                                                      | P0  |
| 同名用户选择      | 搜索到多个同名用户时返回列表，用户回复序号即可选择对应人员                                                  | P0  |
| 时间范围自动识别    | 支持的时间范围：`上个月`/`上月`（默认）`上个季度`/`上季度`自定义格式：`3月`/`2026年3月`/`2026-03`/`Q1`/`2026Q1` | P0  |
| 权限控制        | 配置白名单用户列表：✅ 白名单用户：可查询全公司所有员工考勤❌ 普通用户：仅可查询自己的考勤，查询他人返回无权限提示                     | P0  |
| 错误友好提示      | 无权限、无数据、接口异常、指令格式错误等场景返回可读的提示信息                                                | P0  |
| 结果格式化       | 返回富文本卡片格式，清晰展示考勤各项指标                                                           | P0  |
| 日志审计        | 记录所有查询操作：查询人飞书ID/姓名、查询时间、查询的用户列表、查询时间范围、查询结果状态                                 | P0  |
| Excel导出（可选） | 用户回复`导出`即可将当前查询结果导出为Excel文件发送                                                  | P1  |

***

## 3. 飞书API说明（可直接调用）

### 3.1 通用鉴权

#### 3.1.1 获取tenant\_access\_token（应用级凭证，有效期2小时，需缓存）

```http
POST /auth/v3/tenant_access_token/internal
Content-Type: application/json
Body: {"app_id": "{{FEISHU_APP_ID}}", "app_secret": "{{FEISHU_APP_SECRET}}"}
Response:
{
  "code": 0,
  "tenant_access_token": "t-xxxxxxx",
  "expire": 7200
}
```

缓存逻辑：本地缓存token，距离过期还有10分钟时自动重新获取。

#### 3.1.2 所有API请求头携带鉴权信息：

`Authorization: Bearer {{tenant_access_token}}`

***

### 3.2 通讯录相关API

> **通讯录同步策略：**  
> `GET /contact/v3/users/search` 接口仅支持 `user_access_token`（用户身份），机器人使用的 `tenant_access_token` **无法调用该接口**。  
> 因此本服务采用**定期全量同步通讯录到内存**的方案：服务启动时及每隔1小时自动全量拉取一次员工列表（含工号、姓名、部门、`user_id`、`open_id`），缓存在内存 dict 中，按姓名匹配时直接查内存。  
>
> **多层部门全量同步策略（重要）：**  
> `find_by_department` 接口**只返回指定部门的直属用户**，不递归下级子部门。对于多层部门架构，需先递归拉取完整部门树，再对每个叶子部门（或每个部门逐层）调用 `find_by_department`。  
> 完整同步流程：
> 1. 调用 `GET /contact/v3/departments/children?department_id=0&fetch_child=true` 递归获取所有子部门列表
> 2. 对根部门（`department_id="0"`）及每个子部门逐一调用 `find_by_department` 分页拉取用户
> 3. 去重后合并到内存字典（同一员工可能属于多个部门，以 `user_id` 为唯一键去重）
>
> **飞书开放平台后台必须配置**：`权限管理 → 数据权限 → 通讯录权限范围 → 设置为"全部成员"`，否则接口返回 40041050 无权限错误。

#### 3.2.1 递归获取所有子部门（全量同步第一步）

```http
GET /contact/v3/departments/children
Query Params:
  department_id: str = "0"    # "0" 表示根部门
  fetch_child: bool = true    # 递归获取所有子部门
  page_size: int = 50
  page_token: str = ""
Response 关键字段：
{
  "code": 0,
  "data": {
    "has_more": true,
    "page_token": "xxx",
    "items": [
      {
        "department_id": "d_xxxxxx",
        "open_department_id": "od-xxxxxx",
        "name": "技术部"
      }
    ]
  }
}
```

所需权限：`contact:department.base:readonly`（读取部门基础信息）。

#### 3.2.2 分页拉取部门直属用户列表（全量同步第二步，对每个部门调用）

```http
GET /contact/v3/users/find_by_department
Query Params:
  department_id: str          # 部门ID，根部门传"0"，子部门传对应department_id
  department_id_type: str = "department_id"
  user_id_type: str = "user_id"
  page_size: int = 50
  page_token: str = ""        # 分页翻页token，首次为空
Response 关键字段：
{
  "code": 0,
  "data": {
    "has_more": true,
    "page_token": "xxx",
    "items": [
      {
        "user_id": "u_xxxxxx",
        "open_id": "ou_xxxxxx",
        "name": "张三",
        "employee_no": "10001",
        "department_ids": ["d_xxxxxx"]
      }
    ]
  }
}
```

所需权限：`contact:user.base:readonly`（读取通讯录用户基础信息）。  
同步逻辑：对所有部门（含根部门）逐一分页拉取，以 `user_id` 去重后存入内存字典：`{name: [user_info, ...], open_id: user_info, user_id: user_info}`。

#### 3.2.3 通过 open\_id 查询单个用户详情（用于"查我"场景的 open\_id → user\_id 转换）

```http
GET /contact/v3/users/{user_id}
Query Params:
  user_id_type: str = "open_id"   # 此时 {user_id} path 传 open_id 值
Response 关键字段：
{
  "code": 0,
  "data": {
    "user": {
      "user_id": "u_xxxxxx",
      "open_id": "ou_xxxxxx",
      "name": "张三",
      "employee_no": "10001",
      "department_ids": ["d_xxxxxx"]
    }
  }
}
```

"查我"场景：飞书事件中只能拿到发送者的 `open_id`，需要调用此接口转换为 `user_id` 后才能查询考勤。若内存缓存中已有该用户，直接从缓存取，无需额外调用。

***

### 3.3 考勤相关API

> **考勤统计接口调用说明（重要）：**  
> 飞书考勤统计 API 采用**字段订阅制**，返回的统计字段由预先配置的「统计设置」决定，不会一次性返回所有字段。  
> **完整调用流程分3步：**
> 1. **（首次初始化）** 调用「查询统计表头」获取所有可用字段及其 `code`
> 2. **（首次初始化）** 调用「更新统计设置」，将需要的字段 code 列表保存到当前应用账号下
> 3. **（每次查询）** 调用「查询统计数据」，返回步骤2中配置的字段的统计值
>
> **步骤1和2在服务启动时自动执行**：服务启动时自动调用步骤1获取字段列表并写入内存，同时自动调用步骤2更新统计设置（幂等操作，重复调用安全）。步骤3是每次用户发起查询时的正常调用。若步骤1或步骤2失败，服务记录 ERROR 日志并继续启动，查询时若无字段映射则返回原始 code 作为字段名。

#### 3.3.1 【初始化步骤1】查询统计表头（获取所有可用字段及其 code）

```http
GET /attendance/v1/user_stats_fields/query
Query Params:
  employee_type: str = "employee_id"
  locale: str = "zh"
  stats_type: str = "month"   # daily（每日统计）或 month（月度汇总）
  user_id: str = <调用方自己的 user_id>
Response 关键字段：
{
  "code": 0,
  "data": {
    "user_stats_fields": {
      "stats_type": "month",
      "user_id": "xxx",
      "fields": [
        {
          "code": "50102",
          "title": "姓名",
          "child_fields": []
        },
        {
          "code": "50103",
          "title": "工号",
          "child_fields": []
        }
      ]
    }
  }
}
```

常用字段 code 参考（实际 code 值以接口返回为准，各租户可能略有差异）：

| 字段含义 | 对应字段名 |
|---------|----------|
| 应出勤天数 | 月度汇总字段 |
| 实际出勤天数（工作日） | 月度汇总字段 |
| 迟到次数 | 月度汇总字段 |
| 迟到时长 | 月度汇总字段 |
| 严重迟到次数 | 月度汇总字段 |
| 早退次数 | 月度汇总字段 |
| 早退时长 | 月度汇总字段 |
| 上班缺卡次数 | 月度汇总字段 |
| 下班缺卡次数 | 月度汇总字段 |
| 旷工天数 | 月度汇总字段 |
| 加班总时长 | 月度汇总字段 |
| 请假统计 | 月度汇总字段（含子字段：年假/事假/病假等） |
| 出差天数 | 月度汇总字段 |

> **注意**：字段的具体 `code` 值（如 `50102`）**不是固定的**，每个租户部署后需要先调用此接口获取实际的 code，再写入配置。建议服务启动时自动调用此接口并将 code-title 映射写入内存，作为数据解析的依据。

#### 3.3.2 【初始化步骤2】更新统计设置（配置需要返回的字段）

```http
POST /attendance/v1/user_stats_views/update
Query Params:
  employee_type: str = "employee_id"
Body:
{
  "view": {
    "stats_type": "month",
    "user_id": "<调用方自己的 user_id>",
    "items": [
      {"code": "50102", "child_codes": []},
      {"code": "<迟到次数code>", "child_codes": []},
      {"code": "<迟到时长code>", "child_codes": []},
      {"code": "<早退次数code>", "child_codes": []},
      {"code": "<上班缺卡次数code>", "child_codes": []},
      {"code": "<下班缺卡次数code>", "child_codes": []},
      {"code": "<实际出勤天数code>", "child_codes": []},
      {"code": "<加班总时长code>", "child_codes": []},
      {"code": "<旷工天数code>", "child_codes": []}
    ]
  }
}
```

#### 3.3.3 【每次查询】查询统计数据

```http
POST /attendance/v1/user_stats_datas/query
Query Params:
  employee_type: str = "employee_id"
Content-Type: application/json
Body:
{
  "locale": "zh",
  "stats_type": "month",
  "start_date": 20260301,   # 整数格式 YYYYMMDD，不是时间戳！
  "end_date": 20260331,     # 整数格式 YYYYMMDD，单次请求时间间隔不超过40天
  "user_ids": ["u_xxxxxx"], # 支持批量，单次最多20个user_id
  "user_id": "u_xxxxxx",    # 新系统租户必填（与调用方user_id一致，即FEISHU_ADMIN_USER_ID）
  "need_history": true,
  "current_group_only": false
}
Response 关键字段：
{
  "code": 0,
  "data": {
    "user_datas": [
      {
        "name": "张三",
        "user_id": "u_xxxxxx",
        "datas": [
          {
            "code": "50102",       # 字段code，与统计设置中配置的一致
            "title": "实际出勤天数",  # 字段中文名
            "value": "21",          # 字段值，字符串格式
            "features": [
              {"key": "Abnormal", "value": "false"}
            ]
          }
        ]
      }
    ]
  }
}
```

**数据解析说明：**  
响应中 `datas` 是数组，每项对应一个配置的统计字段。解析时用 `code` 或 `title` 匹配所需字段，`value` 为字符串格式的统计值（时长单位为分钟，需在展示时换算）。`features` 中 `Abnormal=true` 表示该字段存在异常值（如迟到次数>0），可用于前端高亮显示。

**批量查询分批逻辑：**  
- **用户超过20人**：自动将 `user_ids` 按每批20人拆分，串行调用多次后将 `user_datas` 合并
- **时间范围超过40天（如季度查询）**：按月拆分为多次调用（Q1拆分为1月、2月、3月三次调用），每次返回月度汇总，最终按字段求和合并后展示

**季度时间范围对应关系（自然季度）：**

| 指令 | 月份范围 | 拆分调用次数 |
|------|---------|------------|
| Q1 / 上季度（1-3月触发） | 1月1日 - 3月31日 | 3次（按月） |
| Q2 | 4月1日 - 6月30日 | 3次（按月） |
| Q3 | 7月1日 - 9月30日 | 3次（按月） |
| Q4 | 10月1日 - 12月31日 | 3次（按月） |

***

### 3.4 消息相关API

#### 3.4.1 发送文本/卡片消息

```http
POST /im/v1/messages?receive_id_type=open_id
Content-Type: application/json
Body:
{
  "receive_id": "ou_xxxxxx", # 用户open_id
  "msg_type": "interactive", # 卡片消息用interactive，纯文本用text
  "content": "<JSON字符串，卡片内容见3.4.2>"
}
```

#### 3.4.2 考勤结果卡片模板（可直接使用）

```json
{
  "config": {"wide_screen_mode": true},
  "header": {
    "title": {"tag": "plain_text", "content": "📊 考勤查询结果"},
    "template": "blue"
  },
  "elements": [
    {
      "tag": "div",
      "text": {"tag": "lark_md", "content": "**查询对象**：张三\n**查询范围**：2026年3月\n**所属部门**：技术部\n**工号**：10001"}
    },
    {"tag": "hr"},
    {
      "tag": "div",
      "text": {"tag": "lark_md", "content": "✅ 出勤天数：21天\n⚠️ 迟到次数：2次（累计15分钟）\n⚠️ 缺卡次数：1次\n🏖️ 请假天数：1.5天\n⏰ 加班时长：8小时"}
    }
  ]
}
```

#### 3.4.3 多用户选择卡片模板

```json
{
  "config": {"wide_screen_mode": true},
  "header": {
    "title": {"tag": "plain_text", "content": "🔍 找到多个同名用户，请选择"},
    "template": "yellow"
  },
  "elements": [
    {"tag": "div", "text": {"tag": "lark_md", "content": "请回复序号选择查询对象：\n1️⃣ 张三（工号：10001，部门：技术部）\n2️⃣ 张三（工号：10002，部门：市场部）"}}
  ]
}
```

***

## 4. 会话状态管理

### 4.1 同名用户选择状态

当按姓名搜索匹配到多个用户时，需要暂存候选列表，等待用户回复序号。状态存储在内存字典中，key 为用户的 `open_id`，value 为 `{candidates: [...], query_params: {...}}`，超时时间为 5 分钟，超时后自动清除。

**指令解析优先级（重要）：**  
每条消息到达时，处理顺序如下：
1. 首先检查该用户（`open_id`）是否有待确认的同名选择状态
2. 若有，则判断消息是否为纯数字序号（1、2、3…），是则执行选择逻辑，否则清除选择状态后按正常指令处理
3. 若无，则按正常指令匹配规则解析（查/查我/批量查/导出）

### 4.2 批量查询结果展示方式

批量查询（`批量查 姓名1,姓名2 时间范围`）结果以**多张单人卡片**形式依次发送，每张卡片对应一名员工，格式与单人查询卡片相同（见 3.4.2）。若查询人数较多，按查询到结果的顺序逐张发送。

### 4.3 导出上下文状态（P1）

"导出"指令依赖上次查询的结果，同样存储在内存中，key 为 `open_id`，超时时间 10 分钟。

---

## 5. 权限控制规则

1. 白名单配置：通过环境变量 `ALLOWED_USER_IDS` 配置，值为英文逗号分隔的用户open\_id列表，例如：`ALLOWED_USER_IDS=ou_xxx1,ou_xxx2`
2. 权限校验逻辑：
   - 当用户查询他人考勤时，先校验该用户的open\_id是否在白名单中
   - ✅ 白名单用户：允许查询
   - ❌ 普通用户：返回提示「你没有查询他人考勤的权限，仅可查询自己的考勤，发送「查我 上月」即可查询自己的考勤」
3. 所有用户都可以查询自己的考勤，无限制

***

## 6. 服务接口定义

### 6.1 飞书事件回调接口（飞书服务器调用）

```http
POST /webhook/lark/event
Content-Type: application/json
Body: 飞书推送的事件JSON（包含消息内容、发送人信息等）
Response: 200 OK（飞书要求必须5秒内返回200，否则会重试）
```

**处理逻辑：**

1. 使用 **Encrypt Key 加密验证**（飞书事件加密方案）：飞书推送的请求体为加密后的密文，需先用 `FEISHU_ENCRYPT_KEY` 解密后再处理。解密算法：AES-256-CBC，key 为 `SHA256(encrypt_key)` 前32字节，iv 为密文前16字节。解密后得到原始事件 JSON。
2. 如果解密后是URL验证请求（含 `challenge` 字段），直接返回 `{"challenge": "..."}`
3. 消息事件异步处理，先返回 `200 OK` 再执行业务逻辑（FastAPI BackgroundTask），防止飞书重试
4. 解析用户消息内容，按第 4.1 节指令解析优先级匹配处理
5. 执行对应查询逻辑，调用飞书消息接口返回结果

> `FEISHU_VERIFICATION_TOKEN` 保留作为降级校验（可选），Encrypt Key 为主验证方式。

***

## 7. 飞书应用权限清单

飞书开放平台后台需开通以下权限（权限管理 → 添加权限）：

| 权限标识 | 权限说明 | 用途 |
|---------|---------|------|
| `contact:user.base:readonly` | 读取通讯录用户基础信息 | 全量同步员工列表 |
| `contact:department.base:readonly` | 读取部门基础信息 | 递归获取所有子部门列表 |
| `attendance:task:readonly` | 读取打卡数据（查询统计数据/表头/设置） | 查询考勤统计数据 |
| `im:message` | 获取与发送单聊、群组消息 | 接收和发送消息 |
| `im:message:send_as_bot` | 以应用的身份发消息 | 机器人发送卡片消息 |
| `im:message.p2p_msg` | 接收用户发给机器人的单聊消息 | 接收用户查询指令 |

> **后台数据权限配置**：在飞书开放平台 → 权限管理 → 数据权限 → 通讯录权限范围中，需将范围设置为**全部成员**，否则无法获取全员数据。

---

## 8. 环境变量配置

所有敏感配置通过环境变量传入，禁止硬编码：

| 环境变量名                       | 说明                            | 示例                |
| --------------------------- | ----------------------------- | ----------------- |
| FEISHU\_APP\_ID             | 飞书应用AppID                     | `cli_xxxxxx`      |
| FEISHU\_APP\_SECRET         | 飞书应用AppSecret                 | `xxxxxx`          |
| FEISHU\_VERIFICATION\_TOKEN | 飞书事件回调验证Token（降级备用）           | `xxxxxx`          |
| FEISHU\_ENCRYPT\_KEY        | 飞书事件加密密钥（**必填**，用于解密事件请求体）    | `xxxxxx`          |
| FEISHU\_ADMIN\_USER\_ID     | 管理员的 user\_id，用于考勤统计接口的必填参数（获取方式见README） | `u_xxxxxx` |
| ALLOWED\_USER\_IDS          | 可查询全公司考勤的白名单用户open\_id，英文逗号分隔 | `ou_xxx1,ou_xxx2` |
| LOG\_LEVEL                  | 日志级别                          | `INFO`            |
| PORT                        | 服务监听端口                        | `8000`            |

***

## 9. 错误提示规范

| 场景       | 提示文案                                                                                                                                       |
| -------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| 指令格式错误   | "❌ 指令格式不正确，请使用：\n查 \[姓名] \[时间范围] - 查询指定用户考勤\n查我 \[时间范围] - 查询自己的考勤\n批量查 \[姓名1,姓名2] \[时间范围] - 批量查询多个用户考勤\n示例：查 张三 上月 / 查我 Q1 / 批量查 张三,李四 3月" |
| 未找到用户    | "❌ 未找到姓名为「{name}」的员工，请确认姓名是否正确"                                                                                                            |
| 无查询权限    | "❌ 你没有查询他人考勤的权限，仅可查询自己的考勤，发送「查我 上月」即可查询自己的考勤"                                                                                              |
| 无考勤数据    | "ℹ️ {name}在{time\_range}时间段内暂无考勤记录"                                                                                                        |
| 飞书接口异常   | "⚠️ 查询失败，请稍后重试，若多次失败请联系管理员"                                                                                                                |
| 批量查询部分失败 | "⚠️ 部分用户查询失败：{失败用户列表}，其余结果如下："                                                                                                             |

***

## 10. Docker部署配置

需要生成`Dockerfile`和`docker-compose.yml`：

- Dockerfile：基于python:3.11-slim镜像，安装依赖，启动uvicorn服务
- docker-compose.yml：配置环境变量、端口映射、重启策略，可直接`docker-compose up -d`启动

***

## 11. 开发要求

1. 代码结构清晰，分模块：`api/`（接口定义）、`service/`（业务逻辑）、`utils/`（工具类：飞书API封装、时间处理、权限校验等）、`config/`（配置加载）
2. 所有飞书API调用封装成独立工具类，异常捕获处理
3. 日志规范：INFO级别记录正常查询操作，ERROR级别记录异常
4. 遵循PEP8代码规范，添加必要的注释
5. 提供README.md文档，说明部署步骤、配置说明、使用方法
6. 依赖库清单（`requirements.txt`）：
   - `fastapi`、`uvicorn[standard]`：Web框架
   - `httpx`：异步HTTP客户端，用于调用飞书API
   - `python-dotenv`：环境变量加载
   - `pycryptodome`：AES解密，用于飞书事件 Encrypt Key 验证
   - `apscheduler`：定时任务，用于每小时全量同步通讯录
   - `openpyxl`：Excel文件生成（P1导出功能）

