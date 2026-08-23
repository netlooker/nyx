---
name: optic-spark
description: Generate images on the local Optic-Spark GPU worker via optic-cli.
user-invocable: true
disable-model-invocation: false
metadata: {"openclaw": {"requires": {"bins": ["optic-cli"]}}}
---

# Optic-Spark Image Generation

Optic-Spark is your local GPU-accelerated image generation service. Nyx includes the synchronous `optic-cli` (and alias `optic-spark`) tool, which sends generation requests to the Optic-Spark worker, waits for completion via webhook callback, and saves the resulting image to `/data/workspace/images/`.

All API endpoints and host callback network paths are pre-configured automatically via environment variables in Nyx.

## Usage

Run `optic-cli` (or `optic-spark`) directly from the command line:

```bash
optic-cli -prompt "A detailed cyberpunk server room, neon cyan and magenta lighting, cinematic 8k"
```

### Key Parameters

| Flag | Description | Default |
|---|---|---|
| `-prompt` | Text description of the image to generate (**required**) | — |
| `-aspect` | Aspect ratio (`1:1`, `16:9`, `9:16`, `4:3`, `3:2`, `21:9`) | `1:1` |
| `-format` | Output format (`png`, `webp`, `jpeg`) | `png` |
| `-out` | Destination folder for generated image files | `/data/workspace/images` |

### Examples

**1. Generate a widescreen wallpaper:**
```bash
optic-cli -prompt "Hyperrealistic portrait of a robotic fox in a dark cyberpunk alley, rain reflections" -aspect 16:9
```

**2. Generate a mobile / vertical banner:**
```bash
optic-cli -prompt "Retro anime aesthetic synthwave sunset over digital grid landscape" -aspect 9:16 -format webp
```

**3. Generate into a specific subfolder:**
```bash
optic-cli -prompt "Minimalist icon of an obsidian pyramid glowing with blue circuitry" -out /data/workspace/projects/assets
```

## Behavior & Output

- The tool blocks until the GPU finishes generating the image.
- When finished, it prints the absolute path of the saved image.
- Generated images saved to `/data/workspace/images/` persist across container rebuilds and can be viewed directly on the host machine.
