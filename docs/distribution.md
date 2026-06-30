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
three-stage example, and a multiprocessing loader check. Windows artifacts are Authenticode-signed
and timestamped. macOS artifacts are signed during the PyInstaller build with a Developer ID
Application identity, enabling hardened runtime for the executable and all embedded binaries, and
are then submitted to Apple's notarization service.

After all four builds pass, the workflow creates or updates a release in
`DeepPhe/DeepPhe-Dist` using the tag `dphe-db-pipeline-<DPHE_VERSION>` (for example,
`dphe-db-pipeline-7.1`) and uploads all four executables and their SHA-256 checksum files with
replacement enabled.

## Release secrets

Configure these repository-level GitHub Actions secrets in `DeepPhe/dphe-db-pipeline`:

| Secret | Value |
|---|---|
| `DEEPHE_DIST_RELEASE_TOKEN` | Token with `contents:write` access to `DeepPhe/DeepPhe-Dist` |
| `WINDOWS_CERTIFICATE_PFX_BASE64` | Base64-encoded InCommon OV `DeepPhe.pfx` |
| `WINDOWS_CERTIFICATE_PASSWORD` | Password for `DeepPhe.pfx` |
| `MACOS_CERTIFICATE_P12_BASE64` | Base64-encoded Developer ID `DeepPhe.p12` |
| `MACOS_CERTIFICATE_PASSWORD` | Password for `DeepPhe.p12` |
| `APPLE_ID` | Apple ID used for notarization |
| `APPLE_APP_SPECIFIC_PASSWORD` | App-specific password for the Apple ID |
| `APPLE_TEAM_ID` | Apple Developer Team ID associated with the certificate |

The certificate files are small enough for GitHub encrypted secrets. Upload them without adding
them to Git:

```bash
base64 < /secure/path/DeepPhe.pfx | tr -d '\n' |
  gh secret set WINDOWS_CERTIFICATE_PFX_BASE64 --repo DeepPhe/dphe-db-pipeline
gh secret set WINDOWS_CERTIFICATE_PASSWORD --repo DeepPhe/dphe-db-pipeline

base64 < /secure/path/DeepPhe.p12 | tr -d '\n' |
  gh secret set MACOS_CERTIFICATE_P12_BASE64 --repo DeepPhe/dphe-db-pipeline
gh secret set MACOS_CERTIFICATE_PASSWORD --repo DeepPhe/dphe-db-pipeline

gh secret set APPLE_ID --repo DeepPhe/dphe-db-pipeline
gh secret set APPLE_APP_SPECIFIC_PASSWORD --repo DeepPhe/dphe-db-pipeline
gh secret set APPLE_TEAM_ID --repo DeepPhe/dphe-db-pipeline
```

The Linux executable has no platform-native equivalent of Authenticode or Developer ID signing.
The workflow publishes and verifies its SHA-256 checksum, like the other artifacts.
