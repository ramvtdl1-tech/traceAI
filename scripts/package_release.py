"""Build a source-only deployment archive without reading private runtime data."""
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
FILES = (
    '.gitignore', '.env.example', '.streamlit/config.toml', 'README.md',
    'app.py', 'demo_support.py', 'requirements.txt',
    'database/__init__.py', 'database/memory_extractor.py',
    'tests/test_demo.py', 'scripts/check_nebius.py', 'scripts/package_release.py',
)


def main():
    target = ROOT / 'dist/trace-ai-deploy.zip'
    target.parent.mkdir(exist_ok=True)
    with ZipFile(target, 'w', compression=ZIP_DEFLATED) as archive:
        for name in FILES:
            archive.write(ROOT / name, name)
    with ZipFile(target) as archive:
        assert set(archive.namelist()) == set(FILES)
        assert archive.testzip() is None
    print(f'Created {target} ({len(FILES)} source files; no credentials or runtime data)')


if __name__ == '__main__':
    main()
