# 钱途（qiantu-ai-finance）——大学生智能财务管理平台

基于多模态交互与 AI 决策的大学生财务管理 Web 应用（课程项目基础可运行版，内部代号 CSAIFM）。支持电脑浏览器与手机浏览器（响应式），覆盖记账、预算、分析、储蓄目标、提醒、报告与 AI 辅助记账等场景。

- 前端：React 18 + TypeScript（strict）+ Vite 5 + React Router 6 + ECharts 5，中文界面
- 后端：Python 3.12 + FastAPI + SQLAlchemy 2.0（同步 ORM）+ Alembic + psycopg3
- 数据库：**PostgreSQL 16**（需求文档原写 MySQL，按本项目技术栈改为 PostgreSQL，见「待确认事项」）
- 鉴权：JWT（Bearer Token）；密码 bcrypt 哈希存储

> 本轮交付为 Web 版（不包含原生 App）。外部 AI / 语音 / OCR / 邮件服务通过环境变量配置；未配置时接口**明确返回「未配置」**并回退到**标注为演示模式**的本地解析，绝不伪造外部识别结果。代码中不含任何密钥。

---

## 一、快速开始

### 方式 A：本机已有 PostgreSQL（本项目实际验证方式）

要求：PostgreSQL 16、Python 3.12、Node 20+。以下命令以 Windows / PowerShell 为例（Linux/macOS 用对应命令）。

**1. 准备数据库**（一次即可；本机 5432 被占用时用 5433 端口，与默认连接串一致）

```powershell
initdb -D .pgdata -U csaifm -E UTF8                # 在项目根目录初始化数据目录
pg_ctl -D .pgdata -o "-p 5433" -l pg.log start     # 启动，端口 5433
psql -p 5433 -U csaifm -d postgres -c "ALTER USER csaifm PASSWORD 'csaifm';"
createdb -p 5433 -U csaifm csaifm                   # 业务库
createdb -p 5433 -U csaifm csaifm_test              # 测试库（运行 pytest 需要）
```

**2. 启动后端**（首次运行先装依赖）

```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate            # Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head              # 执行数据库迁移
python -m app.seed                # 幂等种子数据：内置分类 + 演示账号
uvicorn app.main:app --reload --port 8000
```

**3. 启动前端**（另开一个终端）

```powershell
cd frontend
npm install
npm run dev                       # 打开 http://localhost:5173
```

开发服务器会把 `/api` 代理到 `http://localhost:8000`（可用环境变量 `VITE_PROXY_TARGET` 覆盖）。

### 方式 B：Docker Compose 一键启动

```powershell
copy .env.example .env            # 建议修改 POSTGRES_PASSWORD 与 JWT_SECRET
docker compose up -d --build
```

启动后：前端 http://localhost:5173 ，API 文档 http://localhost:8000/docs 。容器启动时自动执行迁移与种子数据。

### 演示账号

| 用户名 | 密码 | 说明 |
|---|---|---|
| `demo` | `Demo123456` | 已初始化档案（初始资产 1200 元、生活费 2000 元/月）、近两个月示例账单、预算与储蓄目标、异常消费与预算提醒 |

也可以直接注册新账号：注册 → 首次资料初始化（初始资产/生活费/发放日）→ 记账。

---

## 二、功能清单（对照用户初步需求 USR-0001 ~ 0021）

### ✅ 已实现并通过验证

| 模块 | 功能 |
|---|---|
| 账户（USR-0001~0003） | 注册 / 登录 / JWT 鉴权 / 密码 bcrypt 哈希 / 用户名唯一且不可改 / 登录失败 3 次锁定 15 分钟 / 个人资料与邮箱绑定 / 退出登录 |
| 初始化（USR-0004~0005） | 首次录入可支配资产（作为资产基数）、每月生活费金额与发放日 |
| 记账（USR-0006~0009） | 手动记账（金额/收支类型/分类/可选实际发生时间/可选备注）、账单列表、编辑、删除、分页 |
| 首页（USR-0010） | 资产概览（实时重算）、下次生活费发放倒计时、每日建议支出、本月收支、预算进度与超支风险、最近账单 |
| 分类（USR-0012） | 内置分类（共享、不可修改）、自定义分类、重命名、**软删除（历史账单保留原分类名称快照）** |
| 预算（USR-0013~0014） | 月总预算 + 分类预算、使用率展示、80% 阈值提醒（去重）、月底超支预测（>120% 预算为高风险） |
| 分析（USR-0015） | 日/周/月粒度收支趋势折线图、分类占比条形图（每个图表均有数据表视图）、周期汇总与上期对比、筛选 |
| 储蓄目标（USR-0017） | 目标金额/当前金额/截止日期、进度与风险标签、建议每日储蓄额 |
| 提醒 | 预算提醒 / 异常消费提醒 / 目标提醒，`dedup_key` 防重复，状态恢复自动清除；未读徽标、标记已读 |
| AI 智能记账（USR-0016） | 自然语言草稿解析与批量确认、可编辑草稿（改金额/分类/时间/备注/移除）、语音录入与图片识别入口、AI 消费建议（附依据） |
| 报告（USR-0018, 0020~0021） | 月报/学期报/年报、网页报告预览、PDF 导出（中文）、历史报告列表与删除 |
| 设置 | 生活费修改、资产校准（生成可追溯的「校准」账单）、分类管理、账户信息 |

### 依赖外部密钥配置的功能（未配置时明确提示「未配置」，仅提供标注为演示模式的结果）

| 功能 | 环境变量 | 未配置时行为 |
|---|---|---|
| AI 自然语言解析 / 消费建议 | `AI_API_BASE_URL` + `AI_API_KEY`（OpenAI 兼容） | 本地规则解析器，返回 `mode: "demo"` 并附提示文案；不宣称外部识别已完成 |
| 语音转写 | `SPEECH_API_BASE_URL` + `SPEECH_API_KEY` | 接口返回 503「语音服务未配置」；前端提示改用文字/图片 |
| 图片识别（OCR） | `OCR_API_BASE_URL` + `OCR_API_KEY` | 接口返回 503「图片识别服务未配置」 |
| 邮箱验证码找回密码（USR-0019） | `SMTP_HOST/USER/PASSWORD/FROM` | 接口明确返回「邮件服务未配置」；前端演示流程中验证码仅打印在后端日志（页面已如实提示） |

> 语音/图片通道的**前端交互完整**（录音权限处理、上传、草稿编辑、确认入账），仅缺外部服务密钥。

### 不在本轮范围

- 原生 App（iOS/Android）——按要求本轮只交付 Web 版（已适配手机浏览器）
- 真实外部 AI/语音/OCR 调用（需要密钥，代码适配层已就绪，填入环境变量即可启用）

---

## 三、业务规则与阈值（代码与本文档一致）

### 金额

- 全系统金额一律为**整数分**（`BIGINT`），接口字段后缀 `_cents`；前端元输入通过严格正则 `^\d{1,12}(\.\d{1,2})?$` 转换，**禁止浮点运算**。

### 资产

- 资产**从不落库存储**，始终实时计算：`资产 = 初始资产基数 + 全部收入 − 全部支出 + Σ校准差额`。
- 首次录入的可支配资产是资产基数；账单新增/编辑/删除后资产自动重算。
- 资产校准生成一条 `adjustment` 类型账单（差额可正可负、不可编辑、需重新校准修正），保证可追溯。

### 生活费发放日

- 发放日**只用于周期计算**（倒计时、每日建议支出），**不会自动增加资产**；实际到账请记一笔收入账单。

### 预算提醒与超支预测

- 预警阈值：使用率 ≥ `BUDGET_DEFAULT_THRESHOLD`（默认 **80%**）触发提醒；可在预算设置中按 50~100 调整。
- 超支预测：`本月已支出 + 日均支出 × 剩余天数` 与预算比较；预测 > `FORECAST_HIGH_RISK_FACTOR`（默认 **120%**）预算为高风险，80%~120% 为有风险。
- 提醒防重复：每个用户每条提醒有唯一 `dedup_key`（`budget:{id}` / `anomaly:bill:{bill_id}` / `goal:{id}`）；状态恢复（如调高预算）时自动清除对应提醒。

### 异常消费提醒

| 规则 | 默认值 |
|---|---|
| 单笔 > `ANOMALY_SINGLE_CENTS` | **300 元** |
| 或单笔 > `ANOMALY_SINGLE_FACTOR` × 近 30 天单笔均值（需 ≥ `ANOMALY_SINGLE_MIN_SAMPLES` 笔样本） | **3 倍 / 5 笔** |
| 当日合计 > `ANOMALY_DAILY_FACTOR` × 近 30 天日均，且 > `ANOMALY_DAILY_FLOOR_CENTS` | **2 倍 / 100 元** |

### 数据隔离与安全

- 所有账单/预算/目标/报告按用户隔离；访问其他用户的资源返回 **404**（不暴露资源存在性）。
- 密码只存 bcrypt 哈希；JWT 有效期默认 7 天；密钥只经环境变量注入。

### 自然语言 / 语音 / 图片记账（草稿制）

- 只生成**可编辑草稿**；用户确认后才保存，保存为**全有或全无**（任一草稿无效则整批拒绝，422 `DRAFT_VALIDATION_FAILED`）。
- 取消/失败/缺字段**不会改变任何正式账单**。

### AI 消费建议

- 只能引用**系统实际存在的数据**（账单、预算、目标、资产），每条建议附 `basis` 依据列表；数据不足时明确说明，绝不编造；不修改账单与预算。

### 报告周期

- 月报按自然月；年报按自然年；学期报按可配置学期（默认秋季 09-01 ~ 次年 01-20、春季 02-20 ~ 07-10，环境变量可改）；所有日/月边界按业务时区（默认 `Asia/Shanghai`）计算，数据库存 UTC。

---

## 四、API 与前端约定

- REST API + OpenAPI 文档：启动后端后访问 `http://localhost:8000/docs`。
- 统一错误格式：`{"detail": {"code": "...", "message": "...", "fields": {...}}}`；422 校验错误逐字段提示。
- 时间：接口返回 ISO 8601（UTC）；前端本地化显示（`Asia/Shanghai`）。
- 金额：接口一律整数分（`*_cents`），前端统一在 `utils/money.ts` 转换。

## 五、目录结构

```
├── docker-compose.yml         # 一键启动（db + backend + frontend）
├── .env.example               # 全部环境变量说明
├── backend/
│   ├── app/
│   │   ├── api/               # auth/profile/bills/categories/budgets/analytics/goals/notifications/reports/ai
│   │   ├── models/  schemas/  services/  core/  db/
│   │   └── seed.py            # 幂等种子数据（演示账号、内置分类、示例账单）
│   ├── migrations/            # Alembic（初始迁移 af33fd254bd3）
│   ├── tests/                 # pytest（43 个用例）
│   ├── Dockerfile
│   └── requirements.txt
└── frontend/
    ├── src/
    │   ├── pages/             # 登录/注册/忘记密码/初始化/仪表盘/账单/预算/分析/目标/提醒/报告/AI助手/设置
    │   ├── api/  auth/  components/  utils/  styles/
    │   └── App.tsx            # 路由与鉴权守卫
    ├── Dockerfile + nginx.conf
    └── package.json
```

## 六、测试与验证记录（均已实际执行）

```powershell
# 1) 后端单元/集成测试（backend/）
.venv\Scripts\python.exe -m pytest -q
# => 43 passed in 20.43s（1 个 Starlette 弃用警告，来自测试客户端，不影响运行）
#    覆盖：资产重算、账单增删改、用户数据隔离、预算计算/提醒去重与清除、
#          草稿确认全有或全无、异常阈值与去重、目标指标、报告+PDF、金额往返、演示解析器

# 2) 前端类型检查 + 生产构建（frontend/）
npm run build
# => tsc 严格模式通过；vite 构建通过（dist 约 1.28 MB，gzip 423 KB）

# 3) 端到端验证（backend 运行中，需先执行迁移与种子数据）
.venv\Scripts\python.exe scripts\e2e.py
# => E2E RESULT: ALL PASS（21 项），要点：
#    register → init → bill create/edit/delete 全程资产核对：
#    100000 → 98150（-1850）→ 97650（改 2350）→ 100000（删除）✔
#    isolation: 他人账单 GET /api/bills/1 → 404 ✔
#    speech/ocr 未配置 → 503「未配置」✔
#    NL 演示解析 mode=demo（2 条草稿）/ 消费建议 mode=demo ✔
#    demo 账号：趋势分析 48 个数据点、提醒 12 条、月报生成 + 中文 PDF 下载（%PDF，4659 字节）✔

# 4) 前端链路（vite dev 5173 → 代理 → FastAPI 8000）
#    GET http://localhost:5173/ 返回页面（含 #root）；经代理登录 demo 成功、
#    GET /api/profile 返回 current_assets_cents=263551（种子数据实时重算值）✔
```

数据库迁移与种子数据在真实 PostgreSQL 16（本机端口 5433）上执行验证；**Docker Compose 路径未在本机验证**（本机未运行 Docker），compose/Dockerfile 按标准写法交付，若实际使用遇到问题可按「方式 A」本地启动。

## 八、待确认事项（与需求文档的差异/裁定，均以此版代码为准）

1. **数据库由 MySQL 改为 PostgreSQL**：按本项目技术栈要求执行，ORM 为 SQLAlchemy，迁移由 Alembic 管理。
2. **用户名规则取 SRS 数据词典**：4~12 位、唯一且注册后不可修改。
3. **密码规则**：8~20 位且必须同时包含字母和数字。
4. **登录锁定**：连续 3 次密码错误锁定 15 分钟（SRS 数据词典；可经环境变量调整）。
5. **分类「购物」与「网购」冲突**：初步需求分类含「购物」，SRS 用「网购」——采用 **「网购」**（内置分类），解析关键词覆盖「淘宝/拼多多/京东/买衣服」等。
6. **注册邮箱必填**：按 SRS 3.3.1.1 与 USR-0001，注册须填写合法且全局唯一的邮箱；邮箱用于找回密码（USR-0019，扩展需求），可在「设置 → 账户信息」中更换。SMTP 未配置时验证码仅写后端日志，并明确提示「未配置」。
7. **生活费发放日不自动入账**：需求中「提醒发放日临近」与「记录收入」分开，采用「发放日仅作周期计算，实际到账记收入账单」。
8. **USR-0019~0021 为扩展功能**：本轮已实现（邮箱验证码找回密码、PDF 导出、历史报告列表）；其中邮件发送依赖 SMTP 配置，未配置时验证码仅在后端日志（界面已如实提示）。
9. **金额上限**：单笔金额最多 12 位整数 + 2 位小数（整数分存储，BIGINT）。
