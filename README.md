# 飞书考勤查询机器人

飞书考勤查询机器人，通过单聊消息查询考勤统计数据。

## 功能介绍

通过飞书单聊消息与机器人交互，支持查询指定员工或自己的考勤统计数据，支持多人批量查询，并可导出 Excel 报表。

## 指令说明

| 指令 | 说明 |
|------|------|
| 查 张三 上月 | 查询指定员工上月考勤 |
| 查我 上月 | 查询自己的考勤 |
| 批量查 张三,李四 3月 | 批量查询多人考勤 |
| 导出 | 导出最近一次查询结果为 Excel（开发中） |

支持的时间范围：上月、上季度、3月、2026年3月、2026-03、Q1、Q2、Q3、Q4、2026Q1 等

## 飞书后台配置步骤

1. 在[飞书开放平台](https://open.feishu.cn)创建企业自建应用
2. 开启机器人能力（应用能力 → 添加应用能力 → 机器人）
3. 申请以下权限：
   - `contact:user.base:readonly`
   - `contact:department.base:readonly`
   - `attendance:task:readonly`
   - `im:message`
   - `im:message:send_as_bot`
   - `im:message.p2p_msg`
4. 配置通讯录权限范围：权限管理 → 数据权限 → 通讯录权限范围 → **全部成员**（重要！）
5. 配置事件订阅：
   - 开启加密（Encrypt Key），记录 Encrypt Key 值
   - 添加事件：接收消息 v2.0（im.message.receive_v1）
   - 请求URL填写：`https://your-domain/webhook/lark/event`
6. 发布应用，配置可用范围为全体员工

## 获取 FEISHU_ADMIN_USER_ID

1. 飞书开放平台 → API 调试台
2. 调用"通过手机号或邮箱获取用户 ID"接口
3. 填入管理员手机号，获取 user_id（以 u_ 开头）

## 环境变量配置

| 变量名 | 必填 | 说明 |
|--------|------|------|
| FEISHU_APP_ID | ✅ | 飞书应用 App ID |
| FEISHU_APP_SECRET | ✅ | 飞书应用 App Secret |
| FEISHU_ENCRYPT_KEY | ✅ | 飞书事件加密 Encrypt Key |
| FEISHU_ADMIN_USER_ID | ✅ | 管理员用户 ID（u_开头） |
| FEISHU_VERIFICATION_TOKEN | ❌ | 验证 Token（降级备用） |
| ALLOWED_USER_IDS | ❌ | 可查询他人的用户 open_id，逗号分隔 |
| LOG_LEVEL | ❌ | 日志级别，默认 INFO |
| PORT | ❌ | 服务端口，默认 8000 |

## Docker 部署步骤

```bash
# 1. 克隆仓库
git clone https://github.com/V0N/https---github.com-V0N-FeishuMCP
cd FeishuMCP

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env 填入实际值

# 3. 构建并启动
docker-compose up -d

# 4. 查看日志
docker-compose logs -f

# 5. 验证服务
curl http://localhost:8000/health
```

## 开发运行

```bash
pip install -r requirements.txt
cp .env.example .env  # 填入实际值
uvicorn app.main:app --reload --port 8000
```

## 运行测试

```bash
pytest tests/ -v
pytest tests/ --cov=app --cov-report=term-missing
```
