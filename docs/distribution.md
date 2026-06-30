# Standalone Binary Distribution

PyInstaller produces a self-contained, one-file executable that includes the Python runtime.
The executable temporarily extracts its native libraries when it starts; users do not need to
install Python or project dependencies.

## Artifact matrix

| Artifact | CI runner | Target |
|---|---|---|
| `DeepPheVizDbCreator-linux-x86_64` | `ubuntu-22.04` | glibc-based Linux x86_64 |
| `DeepPheVizDbCreator-windows-x86_64.exe` | `windows-2022` | Windows x86_64 |
| `DeepPheVizDbCreator-macos-arm64` | `macos-15` | Apple Silicon macOS |
| `DeepPheVizDbCreator-macos-x86_64` | `macos-15-intel` | Intel macOS |

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
uv run python packaging/smoke_test.py dist/DeepPheVizDbCreator
```

On Windows, use `dist/DeepPheVizDbCreator.exe` for the smoke-test path.

Build output and PyInstaller work files are written under `dist/` and `build/`, which are ignored.

## CI

The `build-binaries` workflow builds each artifact natively, runs `--help`, the bundled
three-stage example, and a multiprocessing loader check, then renames and uploads each platform
executable as a workflow artifact. It runs manually and on pushes to `main`.

After all four builds pass, the workflow creates or updates an unsigned test release in
`DeepPhe/DeepPhe-Dist` using the tag `dphe-db-pipeline-<DPHE_VERSION>` (for example,
`dphe-db-pipeline-7.1`) and uploads all four executables with replacement enabled. The source
repository must define a `DEEPHE_DIST_RELEASE_TOKEN` secret with `contents:write` access to the
distribution repository.

## Signing boundary

These builds are intentionally unsigned release candidates, and the DeepPhe-Dist release notes
identify them as unsigned. PyInstaller may apply the ad-hoc signature required for executable
code to run on macOS, but no Developer ID identity is used. Developer ID signing and notarization
on macOS, Authenticode signing on Windows, and Linux release signatures are not performed by the
current workflow.
