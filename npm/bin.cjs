#!/usr/bin/env node
/* eslint-disable no-console */
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { spawnSync } = require("node:child_process");

const packageRoot = path.resolve(__dirname, "..");
const runtimeRoot = path.join(os.homedir(), ".session-bridge-plugin", "runtime");
const venvDir = path.join(runtimeRoot, "venv");
const versionFile = path.join(runtimeRoot, "version.json");
const packageJson = JSON.parse(fs.readFileSync(path.join(packageRoot, "package.json"), "utf8"));
const packageVersion = packageJson.version;

function fileExists(p) {
  try {
    fs.accessSync(p);
    return true;
  } catch {
    return false;
  }
}

function runOrFail(cmd, args, opts = {}) {
  const result = spawnSync(cmd, args, { stdio: "inherit", ...opts });
  if (result.status !== 0) {
    process.exit(result.status ?? 1);
  }
}

function findHostPython() {
  if (process.env.PYTHON && process.env.PYTHON.trim()) {
    return process.env.PYTHON.trim();
  }
  for (const candidate of ["python3", "python"]) {
    const res = spawnSync(candidate, ["--version"], { stdio: "ignore" });
    if (res.status === 0) {
      return candidate;
    }
  }
  return "";
}

function pythonInVenv() {
  if (process.platform === "win32") {
    return path.join(venvDir, "Scripts", "python.exe");
  }
  return path.join(venvDir, "bin", "python");
}

function readInstalledVersion() {
  if (!fileExists(versionFile)) {
    return "";
  }
  try {
    const data = JSON.parse(fs.readFileSync(versionFile, "utf8"));
    return String(data.version || "");
  } catch {
    return "";
  }
}

function ensureRuntime(force = false) {
  const pyInVenv = pythonInVenv();
  const installedVersion = readInstalledVersion();
  const needInstall = force || !fileExists(pyInVenv) || installedVersion !== packageVersion;

  if (!needInstall) {
    return pyInVenv;
  }

  const hostPython = findHostPython();
  if (!hostPython) {
    console.error("No host python found. Please install python3 first.");
    process.exit(1);
  }

  fs.mkdirSync(runtimeRoot, { recursive: true });
  runOrFail(hostPython, ["-m", "venv", venvDir]);
  runOrFail(pyInVenv, ["-m", "pip", "install", "--upgrade", "pip"]);
  runOrFail(pyInVenv, ["-m", "pip", "install", "--upgrade", packageRoot]);
  fs.writeFileSync(
    versionFile,
    JSON.stringify(
      {
        version: packageVersion,
        packageRoot,
        updatedAt: new Date().toISOString()
      },
      null,
      2
    ) + "\n",
    "utf8"
  );
  return pyInVenv;
}

function main() {
  const args = process.argv.slice(2);
  const forceSetup = args[0] === "setup-runtime";
  const pyInVenv = ensureRuntime(forceSetup);

  if (forceSetup) {
    console.log(`Runtime ready at ${runtimeRoot}`);
    return;
  }

  const forwarded = [...args];
  if (forwarded[0] === "install-plugin" && !forwarded.includes("--plugin-source")) {
    forwarded.push("--plugin-source", packageRoot);
  }

  const env = { ...process.env };
  const srcPath = path.join(packageRoot, "src");
  env.PYTHONPATH = env.PYTHONPATH ? `${srcPath}${path.delimiter}${env.PYTHONPATH}` : srcPath;
  const result = spawnSync(pyInVenv, ["-m", "codex_session_bridge.cli", ...forwarded], {
    stdio: "inherit",
    env
  });
  process.exit(result.status ?? 1);
}

main();
