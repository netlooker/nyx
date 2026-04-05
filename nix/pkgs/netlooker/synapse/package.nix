{
  python3Packages,
  fetchFromGitHub,
  ...
}:
python3Packages.buildPythonApplication {
  pname = "netlooker-synapse";
  version = "0-unstable-2026-04-05";
  pyproject = true;

  src = fetchFromGitHub {
    owner = "netlooker";
    repo = "synapse";
    rev = "92fac6adc76ae0d7a614f78525c57899bc415680";
    hash = "sha256-8N+mSdA14wJrpr0G+33tlz1pUwOmy7vRSVpy0aTEf1A=";
  };

  postPatch = ''
    substituteInPlace "pyproject.toml" \
      --replace-fail "pydantic-ai" "pydantic-ai-slim"
  '';

  build-system = with python3Packages; [
    uv-build
    setuptools
  ];

  pythonRelaxDeps = [ "sqlite-vec" ];

  # `mcp` is promoted from an optional extra to a core dependency so
  # `synapse-mcp` works out of the box — Nyx always needs the MCP
  # entrypoint, never the bare CLI-only build.
  dependencies = with python3Packages; [
    anyio
    mcp
    numpy
    ollama
    pydantic-ai-slim
    sqlite-vec
  ];

  pythonImportsCheck = [ "synapse" ];
}
