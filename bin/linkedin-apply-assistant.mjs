#!/usr/bin/env node

import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { dirname, delimiter, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const cliModule = "linkedin_apply_assistant.cli";
const userArgs = process.argv.slice(2);
const scriptDir = dirname(fileURLToPath(import.meta.url));
const localSrc = resolve(scriptDir, "..", "src");
const launcherEnv = { ...process.env };
const candidates =
  process.platform === "win32"
    ? [
        ["py", ["-3"]],
        ["python", []],
        ["python3", []],
      ]
    : [
        ["python3", []],
        ["python", []],
      ];

if (existsSync(localSrc)) {
  launcherEnv.PYTHONPATH = launcherEnv.PYTHONPATH
    ? `${localSrc}${delimiter}${launcherEnv.PYTHONPATH}`
    : localSrc;
}

function printSetupGuidance(reason) {
  console.error(`linkedin-apply-assistant npm launcher could not start: ${reason}`);
  console.error("");
  console.error("This npm package is only a thin launcher for the Python package.");
  console.error("Install the Python package from the package root, then retry:");
  console.error("  python -m pip install .");
  console.error('  python -m pip install -e ".[dev]"');
  console.error("  pipx install <future-source>");
  console.error("");
  console.error("Module fallback after source checkout:");
  console.error("  python -m linkedin_apply_assistant.cli --help");
}

function runPython(command, args, options = {}) {
  return spawnSync(command, args, {
    env: launcherEnv,
    windowsHide: true,
    ...options,
  });
}

let sawPython = false;

for (const [command, prefixArgs] of candidates) {
  const probe = runPython(command, [...prefixArgs, "-c", `import ${cliModule}`], {
    stdio: "ignore",
  });

  if (probe.error?.code === "ENOENT") {
    continue;
  }

  if (probe.error) {
    continue;
  }

  sawPython = true;

  if (probe.status !== 0) {
    continue;
  }

  const result = runPython(command, [...prefixArgs, "-m", cliModule, ...userArgs], {
    stdio: "inherit",
  });

  if (result.error) {
    printSetupGuidance(result.error.message);
    process.exit(1);
  }

  if (result.signal) {
    console.error(`Python CLI exited after signal ${result.signal}`);
    process.exit(1);
  }

  process.exit(result.status ?? 1);
}

printSetupGuidance(
  sawPython
    ? "Python was found, but the linkedin_apply_assistant package is not importable."
    : "No usable Python executable was found on PATH.",
);
process.exit(1);
