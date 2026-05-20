#!/usr/bin/env node
import { spawnSync, spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import process from "node:process";

const rootDir = path.resolve(path.dirname(new URL(import.meta.url).pathname));
const backendDir = path.join(rootDir, "backend");
const frontendDir = path.join(rootDir, "frontend");

const backendPort = process.env.BACKEND_PORT ?? "3000";
const frontendPort = process.env.FRONTEND_PORT ?? "5173";
const bindHost = process.env.BIND_HOST ?? "0.0.0.0";

const possiblePython = [
  path.join(backendDir, ".venv", "Scripts", "python.exe"),
  path.join(backendDir, ".venv", "bin", "python"),
  process.env.PYTHON,
  "python",
  "python3",
  "py",
].filter(Boolean);

function resolvePython() {
  for (const candidate of possiblePython) {
    try {
      if (path.isAbsolute(candidate) && !fs.existsSync(candidate)) {
        continue;
      }
      const result = spawnSync(candidate, ["--version"], {
        stdio: "ignore",
        shell: false,
      });
      if (result.status === 0) {
        return candidate;
      }
    } catch {
      continue;
    }
  }
  return null;
}

const pythonPath = resolvePython();
if (!pythonPath) {
  console.error(
    "未找到可用的 Python 解释器。请设置 PYTHON 环境变量或确保 python/py 在 PATH 中。",
  );
  process.exit(1);
}

const npmCommand = process.platform === "win32" ? "npm.cmd" : "npm";
const useShellForNpm = process.platform === "win32";
let backendProcess;
let frontendProcess;

function stopAll(exitCode = 0) {
  if (backendProcess && !backendProcess.killed) {
    backendProcess.kill();
  }
  if (frontendProcess && !frontendProcess.killed) {
    frontendProcess.kill();
  }
  process.exit(exitCode);
}

function start(name, command, args, options = {}) {
  const child = spawn(command, args, {
    shell: false,
    stdio: "inherit",
    ...options,
  });

  child.on("exit", (code, signal) => {
    if (signal) {
      console.log(`${name} 进程收到信号 ${signal} 退出`);
    } else {
      console.log(`${name} 进程退出，code=${code}`);
    }
    if (code !== 0 || signal) {
      stopAll(code ?? 1);
    }
  });

  child.on("error", (error) => {
    console.error(`${name} 启动失败:`, error.message ?? error);
    stopAll(1);
  });

  return child;
}

process.on("SIGINT", () => stopAll(0));
process.on("SIGTERM", () => stopAll(0));

console.log("正在启动开发环境，后端与前端热加载将同时运行...");
console.log(`后端: host=${bindHost} port=${backendPort}`);
console.log(`前端: host=${bindHost} port=${frontendPort}`);

backendProcess = start(
  "backend",
  pythonPath,
  [
    "-m",
    "uvicorn",
    "app.main:app",
    "--reload",
    "--host",
    bindHost,
    "--port",
    backendPort,
  ],
  { cwd: backendDir },
);

frontendProcess = start(
  "frontend",
  npmCommand,
  ["run", "dev", "--", "--host", bindHost, "--port", frontendPort],
  { cwd: frontendDir, shell: useShellForNpm },
);
