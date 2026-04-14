#!/usr/bin/env node
/* eslint-disable no-console */
const path = require("node:path");
const { spawnSync } = require("node:child_process");

const packageRoot = path.resolve(__dirname, "..");
const bridgeBin = path.join(__dirname, "bin.cjs");

const skipAuto = process.env.SESSION_BRIDGE_SKIP_AUTO_INSTALL === "1";
const forceAuto = process.env.SESSION_BRIDGE_AUTO_INSTALL === "1";
const isGlobalInstall =
  process.env.npm_config_global === "true" || process.env.npm_config_location === "global";

function log(message) {
  console.log(`[session-bridge postinstall] ${message}`);
}

function main() {
  if (skipAuto) {
    log("skip: SESSION_BRIDGE_SKIP_AUTO_INSTALL=1");
    return;
  }

  if (!forceAuto && !isGlobalInstall) {
    log("skip: local install detected (set SESSION_BRIDGE_AUTO_INSTALL=1 to force)");
    return;
  }

  const reason = forceAuto ? "forced by SESSION_BRIDGE_AUTO_INSTALL=1" : "global install detected";
  log(`running plugin registration (${reason})`);
  const result = spawnSync(
    process.execPath,
    [bridgeBin, "install-plugin", "--plugin-source", packageRoot],
    { stdio: "inherit", env: process.env }
  );

  if (result.error) {
    log(`warning: plugin auto-install failed (${result.error.message})`);
    return;
  }

  if (typeof result.status === "number" && result.status !== 0) {
    log(`warning: plugin auto-install exited with code ${result.status}`);
    return;
  }

  log("plugin auto-install completed");
}

main();
