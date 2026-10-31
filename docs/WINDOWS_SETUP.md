# Windows 本地运行与验收

## 日常使用：双击启动

在项目根目录双击 **启动OntoForge.cmd**。它会检查本地依赖、连接或启动项目 Neo4j、在后台启动前后端并自动打开浏览器。首次缺少依赖时会自动安装到本项目；需要先安装 Python 3.11、Node.js 和 Docker Desktop。已经运行时再次双击只打开页面，不重复启动。

结束时双击 **停止OntoForge.cmd**。它只停止该启动器创建的前后端进程；数据库、论文、模型接口配置和用户账户都会保留。不运行演示数据加载器。

启动失败时窗口会保留错误提示。日志在 `backend/data/launcher/backend.log` 和 `frontend.log`。默认访问 `http://127.0.0.1:5173`，后端端口 8765。端口冲突不会自动结束其他程序；可在 `.env` 设置 `ONTOFORGE_FRONTEND_PORT` 和 `ONTOFORGE_BACKEND_PORT`，停止后再启动。

命令行也可以使用：

```powershell
.\backend\.venv\Scripts\python.exe scripts/local_launcher.py start
.\backend\.venv\Scripts\python.exe scripts/local_launcher.py status
.\backend\.venv\Scripts\python.exe scripts/local_launcher.py stop
```

前后端常规启动使用已有 `.env` 和正常数据目录，与隔离的自动演示流程分开。已有数据库的密码不匹配时会提示修改配置，启动器不会重置数据库密码或清空数据库。停止操作以 PID 和进程创建时间双重核对，避免 PID 被复用后误停其他程序。

## 首次安装与手动操作

在 PowerShell 中，从项目根目录操作。需要 Python 3.11、Node.js/npm、Docker Desktop。数据库数据与应用配置分别备份；不要用正常研究数据库运行集成测试。

```powershell
python -m venv backend/.venv
.\backend\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
Copy-Item .env.example .env   # 仅首次配置；已有 .env 不要覆盖
Push-Location frontend
npm ci
npx playwright install chromium
Pop-Location
docker compose up -d neo4j
```

编辑 `.env` 配置数据库连接。模型接口现在可在登录后的右下角“模型接口”中新增、保存和切换，无需手改 `.env`；操作见 [接口配置说明](LLM_PROFILES.md)。`.env` 仍作为可选的服务器默认配置。不要提交密钥，也不要把密钥放进 PPT 或日志。未配置模型时的规则链路不证明真实 LLM 完成任务。

启动后端：

```powershell
.\backend\.venv\Scripts\python.exe -m uvicorn backend.server.app:app --host 127.0.0.1 --port 8765
```

另一个终端启动前端：

```powershell
Set-Location frontend
npm run dev
```

访问 `http://localhost:5173`。本地演示账户默认 demo/demo1234；实际部署应关闭自动演示账户或修改密码。新建自己的工作区，添加领域包后上传论文。`cv_detection` 是本次新增的 CV 检测领域包。

每篇论文先预览，再确认入库。提交携带 `preview_id`，保存服务器侧预览快照；配置变更、上传过期或部分批次失败时必须重新预览。历史浏览器队列若没有 preview_id，请重试或重新上传。

原始 PDF 保存在 `backend/data/sources`（可用 `ONTOFORGE_SOURCE_DIR` 修改），论文文本与断言存 Neo4j，用户账户另存本地用户文件。完整备份应同时包含这些数据。原始 PDF 只能通过有工作区读权限的 `getPaperSource` 下载，证据面板提供下载按钮；旧数据与模拟论文没有原始 PDF 时会明确提示。pypdf 仅提供页码，界面不把占位坐标当精确区域。

## 自动验收

```powershell
.\scripts\test_all.ps1
```

脚本会创建全新的测试容器和随机端口，运行后端全部测试、真实 Neo4j 测试、类型检查、lint、生产构建和 Playwright 六视图演示。结束后停止该容器。截图存 `frontend/demo-screenshots`，演示服务日志存 `.demo/windows`。这些六视图使用明确标识的模拟数据；另有真实数据库上的 PDF 上传→预览→提交→证据→双用户隔离 API 测试。两者都不能代替真实 LLM 的科研质量评估。

仅做快速检查可用：

```powershell
.\scripts\test_all.ps1 -SkipIntegration -SkipBrowser
```

这只算部分检查。完整脚本不会把缺失 Docker、被跳过的集成或浏览器失败算成成功。

单独运行集成测试时，只设置 `ONTOFORGE_TEST_NEO4J_URI` 指向**可清空的专用数据库**，并配置对应 `NEO4J_USER` / `NEO4J_PASSWORD`。测试会清空该数据库。已移除从应用 `NEO4J_URI` 自动选取集成测试目标的行为，避免误删正常研究数据。

## CV 样本与后期验证

```powershell
.\backend\.venv\Scripts\python.exe -m backend.scripts.prepare_cv_corpus --split historical
.\backend\.venv\Scripts\python.exe -m backend.scripts.check_cv_parsing
```

12 篇历史 PDF 放在 `data/cv-validation/historical`。后期 7 篇的列表及公平时间切分协议见 `docs/cv-validation/README.md`。必须冻结历史候选结果，再使用后期文献评估；不能用人工预先列举的方向冒充系统已经预测命中。

## 已知运行边界

- 当前版本未做 Electron 安装包的发布与签名验收；本次浏览器前端验收与 Electron 打包验收分别对待。
- 原始 PDF 文件归档与 Neo4j 不是跨系统分布式事务；数据库回滚后可能留下不可通过 API 访问的孤立归档文件。图谱写入本身为一个事务。
- 领域包绑定和待入库队列仍包含浏览器本地状态，跨设备同步尚未实现。
- 升级旧数据不会自动将旧 paper_id 迁移为新作用域 ID；新导入使用工作区+领域包+内容哈希。旧数据应先备份再制定迁移策略。
- 真实模型调用、质量标注及未来覆盖回测需另附实际实验记录，不能由本脚本自动宣称完成。
