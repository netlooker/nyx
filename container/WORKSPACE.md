# Workspace

This is your persistent workspace. Everything here survives container rebuilds.

## Structure

```text
workspace/
  services/      — long-running processes with UI or API (dashboards, web apps)
  tools/         — CLIs, scripts, and utilities you install
  projects/      — git repos you work on (clone here, each gets its own venv/node_modules)
```

## Rules

- Clone repos into `projects/`. Do not put loose code at the workspace root.
- Install CLI tools into `tools/`. Keep each tool in its own subdirectory.
- Services that expose a port or run continuously go in `services/`.
- Scratch files and temporary work go at the workspace root — clean up when done.
- Each project manages its own dependencies (venv, node_modules) inside its directory.
