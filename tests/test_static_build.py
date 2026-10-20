import subprocess
import sys
from pathlib import Path


def test_static_build_creates_missing_output_without_app_import(tmp_path):
    for filename in ("build_site.py", "legal.py"):
        (tmp_path / filename).write_text(
            Path(filename).read_text(encoding="utf-8"), encoding="utf-8"
        )
    assert not (tmp_path / "site").exists()
    result = subprocess.run(
        [sys.executable, "build_site.py"], cwd=tmp_path, capture_output=True, text=True, check=True
    )
    assert "wrote" in result.stdout
    for filename in ("privacy.html", "terms.html"):
        output = (tmp_path / "site" / filename).read_text(encoding="utf-8")
        assert "<!doctype html>" in output
        assert "review required" in output
        assert "fonts.googleapis.com" not in output
