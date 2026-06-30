# Standalone Binary Distribution

PyInstaller produces a self-contained, one-file executable that includes the Python runtime.
The executable temporarily extracts its native libraries when it starts; users do not need to
install Python or project dependencies.

## Artifact matrix

| Artifact | CI runner | Target |
|---|---|---|
| `dphe-pipeline-linux-x86_64` | `ubuntu-22.04` | glibc-based Linux x86_64 |
| `dphe-pipeline-windows-x86_64.exe` | `windows-2022` | Windows x86_64 |
| `dphe-pipeline-macos-arm64` | `macos-15` | Apple Silicon macOS |
| `dphe-pipeline-macos-x86_64` | `macos-15-intel` | Intel macOS |

Alpine/musl Linux and other CPU architectures require separate native builds.

## Embedded resources

The executable contains:

- the bundled example DeepPhe output and demographics data;
- `omop-config.js`;
- the curated 52-row ICD cancer mapping;
- the project `LICENSE` and `NOTICE`;
- license metadata for the embedded runtime dependencies and PyInstaller bootloader.

SNOMED data is not used or embedded. The binary build installs the optional MySQL connector so
that JSON, CSV, and MySQL source modes are all available in the same executable.

## Local unsigned build

Run the build on the operating system and CPU architecture being targeted:

```bash
uv sync --frozen --group binary --extra mysql
uv run pyinstaller --clean --noconfirm packaging/dphe-pipeline.spec
uv run python packaging/smoke_test.py dist/dphe-pipeline
```

On Windows, use `dist/dphe-pipeline.exe` for the smoke-test path.

Build output and PyInstaller work files are written under `dist/` and `build/`, which are ignored.

## CI

The `build-binaries` workflow builds each artifact natively, runs `--help` and the bundled
three-stage example, renames the platform executable, and uploads it as a workflow artifact.
It runs manually and for version tags matching `v*`.

## Signing boundary

These builds are intentionally unsigned release candidates. PyInstaller may apply the ad-hoc
signature required for executable code to run on macOS, but no Developer ID identity is used.
Developer ID signing and notarization on macOS, Authenticode signing on Windows, and Linux
release signatures are the next distribution stage and are not performed by the current
workflow.
