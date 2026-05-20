# Word Practice

项目范围：

- 支持用户注册与登录
- 支持词库导入并忽略重复词条
- 支持从全部词库或错题本随机练习
- 练习页面仅填空缺失字母，判定忽略大小写
- 统计以提交次数聚合
- 支持练习历史记录查看

技术栈：后端使用 FastAPI + Python，前端使用 React + Vite，开发服务器由 `uvicorn` 和 `npm run dev` 提供。

## Backend (FastAPI)

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 3000 --host 0.0.0.0
```

后端默认监听：`http://127.0.0.1:3000`

可选 `.env` 配置：

```env
# 缺失字母比例（0.1 ~ 0.9），默认 0.5
WORD_MISSING_RATIO=0.5
```

## Frontend (React + Vite)

```bash
cd frontend
npm install
npm run dev
```

Frontend default URL: `http://127.0.0.1:5173`

Vite已配置 **`server.host: true`**，`npm run dev` 时不要加 `--host 127.0.0.1`。同一局域网可用 **`http://<本机局域网 IP>:5173`**。开发模式下接口走 **Vite 代理** `/api` → 本机 `3000`。打包或直连后端时可设 `VITE_API_BASE_URL`。

## Scripts

根目录提供脚本以简化依赖安装、开发调试和生产启动：

- 开发环境：
  - `node start.js`
    - 启动后端 `uvicorn` 开发服务器（`--reload`）
    - 启动前端 Vite 开发服务器，支持热加载
- Windows PowerShell:
  - `.
scripts\install-deps.ps1`
  - `.
scripts\start-prod.ps1`
- Unix / macOS / Linux:
  - `./scripts/install-deps.sh`
  - `./scripts/start-prod.sh`

`install-deps` 脚本会在 `backend/.venv` 中创建 Python 虚拟环境并安装 `backend/requirements.txt`，同时在 `frontend` 中执行 `npm ci`。

`start-prod` 脚本会先构建前端产物，再启动后端 `uvicorn` 和前端 `npm run preview`，默认绑定 `0.0.0.0`，并使用端口 `3000` / `5173`。可通过环境变量 `BACKEND_PORT`、`FRONTEND_PORT`、`BIND_HOST` 调整。

> Windows 如遇执行策略限制，可用 `powershell -ExecutionPolicy Bypass -File .\scripts\install-deps.ps1`。

## CSV Import Format

表头至少包含 `word`、`translation`；可选 `phonetic`、`part_of_speech`（也可用列名 `pos`）。

多词性时建议在 `translation` 中分段书写，例如：`名词 n. 图书馆；动词 v. 反对`。

前端页面「单词本」提供导入弹窗，并可下载样例文件：`/sample-vocab.csv`（开发环境下由 `frontend/public/sample-vocab.csv` 提供）。

```csv
word,translation,phonetic,part_of_speech
apple,名词 n. 苹果；苹果树,ˈæpəl,n.
record,名词 n. 记录；动词 v. 记下,rɪˈkɔːd,n.;v.
```

## Migrate Old User Data

如果你有旧版本的 `word_practice.db`，可将其统计数据（练习记录、统计快照）与错题本相关词条迁入当前库：

```bash
cd backend
source .venv/bin/activate
python -m app.migrate_external_user_data \
  --source-db "/path/to/old/word_practice.db" \
  --source-username admin \
  --target-username admin
```

迁移会做去重并合并：
- 词条按单词去重导入到当前词库（仅迁入错题/练习记录引用到的词）。
- 错题本按 `(user_id, vocabulary_id)` 合并。
- 练习记录与统计快照按内容签名去重后写入。
