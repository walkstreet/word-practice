# Word Practice

V1 scope:
- User system enabled (register/login)
- Vocabulary import with duplicate skip
- Random practice from full vocabulary or wrong book
- User inputs missing letters only, judging ignores case only
- Stats aggregated by submission count
- Practice history list supported

## Backend (FastAPI)

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# 监听 0.0.0.0：便于本机以外访问（如 Docker / Dify 容器通过 host.docker.internal 连到本机后端）
uvicorn app.main:app --reload --port 3000 --host 0.0.0.0
```

本机浏览器访问：`http://127.0.0.1:3000`。若 **Docker 内**（含 Dify）访问宿主机上的本服务，请使用 `http://host.docker.internal:3000`；**必须**加上 `--host 0.0.0.0`，否则只绑 `127.0.0.1` 时容易出现**连接被拒绝 / 网关 502**。

### Dify / 工作流仍为 502 时

1. **先测连通**（需在 Header 里带 `x-api-key`，与 `.env` 里 `DIFY_IMPORT_API_KEY` 一致）：`GET http://host.docker.internal:3000/api/dify/ping` 应返回 `{"status":"ok","service":"word-practice"}`。若这里也 502，多半是 **Dify 侧代理/SSRF** 或网络，不是本仓库业务代码。
2. **自托管 Dify** 对工作流里的 HTTP 请求常走 **SSRF 代理**，可能拦截访问宿主机/内网。需在 Dify 文档或 `ssrf_proxy`（Squid）配置中放行对应地址，或对 API 容器配置可绕过代理的地址（参见 [Dify Docker 故障排查](https://docs.dify.ai/self-host/troubleshooting/docker-issues) 与相关 issue）。
3. 确认请求 URL 为 **`http://` 而非 `https://`**（本开发服务一般未开 TLS）。
4. **Linux** 若无 `host.docker.internal`，可改用宿主机在局域网中的 IP（如 `192.168.x.x`），或为容器增加 `extra_hosts`（如 `host.docker.internal:host-gateway`）。

Optional backend config in `.env`:

```env
# Missing letter ratio (0.1 ~ 0.9), default 0.5
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

## CSV Import Format

表头至少包含 `word`、`translation`；可选 `phonetic`、`part_of_speech`（也可用列名 `pos`）。

多词性时建议在 `translation` 中分段书写，例如：`名词 n. 图书馆；动词 v. 反对`。

前端页面「单词本」提供导入弹窗，并可下载样例文件：`/sample-vocab.csv`（开发环境下由 `frontend/public/sample-vocab.csv` 提供）。

```csv
word,translation,phonetic,part_of_speech
apple,名词 n. 苹果；苹果树,ˈæpəl,n.
record,名词 n. 记录；动词 v. 记下,rɪˈkɔːd,n.;v.
```
