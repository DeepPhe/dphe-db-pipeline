from pathlib import Path

from PyInstaller.utils.hooks import copy_metadata


project_root = Path(SPECPATH).parent
package_root = project_root / "src" / "dphe_db_pipeline"

# Keep the data-file destinations aligned with their source-package paths.
# dphe_db_pipeline.paths uses __file__-relative paths in normal and frozen runs.
datas = [
    (
        str(package_root / "resources" / "example"),
        "dphe_db_pipeline/resources/example",
    ),
    (
        str(package_root / "omop_importer" / "omop-config.js"),
        "dphe_db_pipeline/omop_importer",
    ),
    (
        str(package_root / "omop_importer" / "lookup_tables" / "ICD_CODES"),
        "dphe_db_pipeline/omop_importer/lookup_tables/ICD_CODES",
    ),
    (str(project_root / "LICENSE"), "."),
    (str(project_root / "NOTICE"), "."),
]

# Preserve the licenses and package metadata for dependencies embedded in the executable.
for distribution in (
    "mysql-connector-python",
    "pyinstaller",
    "pyroaring",
    "python-dotenv",
    "zstandard",
):
    datas += copy_metadata(distribution)

analysis = Analysis(
    [str(project_root / "pipeline.py")],
    pathex=[str(project_root / "src")],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(analysis.pure)

executable = EXE(
    pyz,
    analysis.scripts,
    analysis.binaries,
    analysis.datas,
    [],
    name="dphe-pipeline",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
