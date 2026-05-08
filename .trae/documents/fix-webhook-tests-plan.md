# 修复 test_webhook.py 3个失败测试的开发计划

## 问题分析

### 根本原因
`tests/test_webhook.py` 使用 `os.environ.setdefault("FEISHU_ENCRYPT_KEY", TEST_ENCRYPT_KEY)` 设置加密密钥，但这种方式存在严重问题：

1. **`setdefault` 不覆盖已有值**：如果其他测试文件（如 `test_integration.py`）在 `test_webhook.py` 之前导入并初始化了 settings，或者 CI 环境中已有该环境变量，`setdefault` 不会修改它。

2. **settings 单例在模块导入时初始化**：`app/config/settings.py` 的最后两行：
   ```python
   try:
       settings = load_settings()  # 模块首次导入时执行，之后缓存
   except ValueError:
       settings = None
   ```
   一旦 `settings` 单例被初始化，`app/api/webhook.py` 中的 `from app.config.settings import settings` 就固定了对该对象的引用。

3. **结果**：webhook 解密用的 `settings.FEISHU_ENCRYPT_KEY` 与测试加密用的 `TEST_ENCRYPT_KEY` 不同，导致 `DecryptError` → 返回 400。

### 失败的3个测试
- `test_url_verification` - 期望 200，实际 400（解密失败）
- `test_message_event_returns_200` - 期望 200，实际 400（解密失败）
- `test_non_message_event_ignored` - 期望 200，实际 400（解密失败）

### 正常工作的测试
- `test_decrypt_failure_returns_400` - 期望 400，实际也是 400（但原因不同：这个测试用的是无效密文，即使 key 正确也会解密失败，所以恰好通过）

---

## 修复方案

### 方案：使用 `monkeypatch` + `patch.object` 在 fixture 中直接替换 settings 的 FEISHU_ENCRYPT_KEY

**原理**：在 `client` fixture 中，使用 `unittest.mock.patch.object` 直接替换已初始化的 `settings` 对象的 `FEISHU_ENCRYPT_KEY` 属性，确保 webhook 使用的 key 与测试加密时使用的 key 一致。

这比 `importlib.reload` 方案更简单，因为：
- 无需重载模块
- 无需重建所有服务单例
- `webhook.py` 中用的是 `settings.FEISHU_ENCRYPT_KEY`（属性访问），patch 对象属性可以直接生效

**实现方式**：

将 `test_webhook.py` 的 `client` fixture 从：
```python
@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)
```

改为：
```python
@pytest.fixture
def client():
    import app.config.settings as settings_mod
    from app.main import app
    
    # 确保环境变量已设置（为了 settings 能成功初始化）
    # 使用 patch.object 直接替换 settings 单例的 FEISHU_ENCRYPT_KEY
    with patch.object(settings_mod, "settings", settings_mod.load_settings({
        "FEISHU_APP_ID": "test_app_id",
        "FEISHU_APP_SECRET": "test_app_secret",
        "FEISHU_ENCRYPT_KEY": TEST_ENCRYPT_KEY,
        "FEISHU_ADMIN_USER_ID": "test_admin_user",
    })):
        yield TestClient(app)
```

这种方式：
1. 调用 `load_settings({...})` 创建一个使用 `TEST_ENCRYPT_KEY` 的新 Settings 对象
2. 用 `patch.object` 将 `settings_mod.settings`（模块级变量）替换为这个新对象
3. `webhook.py` 中 `from app.config.settings import settings` 导入的是同一个模块引用，会读到被 patch 后的值

> **注意**：`webhook.py` 的第8行是 `from app.config.settings import settings`，这是将 `settings` 对象的引用绑定到了 `app.api.webhook` 模块的命名空间。因此需要同时 patch `app.api.webhook` 模块中的 `settings` 引用。

### 最终修复方案（双重 patch）

同时 patch 两处：
1. `app.config.settings.settings` — 模块级变量
2. `app.api.webhook.settings` — webhook 模块中导入的引用

```python
@pytest.fixture
def client():
    import app.config.settings as settings_mod
    import app.api.webhook as webhook_mod
    from app.main import app
    
    test_settings = settings_mod.load_settings({
        "FEISHU_APP_ID": "test_app_id",
        "FEISHU_APP_SECRET": "test_app_secret",
        "FEISHU_ENCRYPT_KEY": TEST_ENCRYPT_KEY,
        "FEISHU_ADMIN_USER_ID": "test_admin_user",
    })
    
    with patch.object(settings_mod, "settings", test_settings), \
         patch.object(webhook_mod, "settings", test_settings):
        yield TestClient(app)
```

---

## 执行步骤

### Step 1：修复 test_webhook.py 的 client fixture
- 修改 `tests/test_webhook.py`
- 将 `client` fixture 改为使用双重 `patch.object` 方式
- 同时移除顶层 `os.environ.setdefault` 调用（改为在 fixture 内部通过字典传入）

### Step 2：运行 test_webhook.py 确认4个测试全部通过
```bash
cd /Users/gangwang/Documents/trae_projects/FeishuMCP
python -m pytest tests/test_webhook.py -v
```

### Step 3：运行全量测试确认 109/109 全部通过
```bash
cd /Users/gangwang/Documents/trae_projects/FeishuMCP
python -m pytest --tb=short -q
```

---

## 预期结果

全量测试：**109 passed, 0 failed**
