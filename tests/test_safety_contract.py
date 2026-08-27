from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_runtime_has_no_database_email_or_network_adapters():
    runtime = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (REPO_ROOT / "src" / "discount_curve_demo").glob("*.py")
    ).lower()
    forbidden_runtime_dependencies = (
        "pyodbc",
        "win32com",
        "sqlalchemy",
        "smtplib",
        "requests",
        "urllib.request",
    )

    assert all(marker not in runtime for marker in forbidden_runtime_dependencies)


def test_fixture_is_explicitly_synthetic_and_contains_no_free_text_columns():
    header = (
        (REPO_ROOT / "data" / "synthetic_market_data.csv")
        .read_text(encoding="utf-8")
        .splitlines()[0]
    )

    assert header == "as_of_date,currency,curve_type,tenor,value"


def test_public_surface_contains_no_workstation_or_automation_markers():
    roots = [
        REPO_ROOT / "src",
        REPO_ROOT / "config",
        REPO_ROOT / "data",
        REPO_ROOT / "docs",
        REPO_ROOT / ".github",
    ]
    paths = [
        REPO_ROOT / "README.md",
        REPO_ROOT / "SECURITY.md",
        REPO_ROOT / "CONTRIBUTING.md",
        REPO_ROOT / "pyproject.toml",
    ]
    text_suffixes = {".csv", ".md", ".py", ".toml", ".yaml", ".yml"}
    paths.extend(
        path
        for root in roots
        for path in root.rglob("*")
        if path.is_file() and path.suffix in text_suffixes
    )
    public_text = "\n".join(path.read_text(encoding="utf-8") for path in paths).lower()
    forbidden_markers = (
        "/users/",
        "c:\\users\\",
        "outlook.application",
        "win32com",
        "pyodbc",
        "oracle+",
        "smtp://",
    )

    assert all(marker not in public_text for marker in forbidden_markers)
