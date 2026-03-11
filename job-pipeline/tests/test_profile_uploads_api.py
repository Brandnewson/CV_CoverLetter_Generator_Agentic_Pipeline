"""Tests for profile upload API duplicate filename handling."""

from io import BytesIO
from pathlib import Path
from unittest.mock import patch

import pytest

from dashboard.cv_builder_ui import app, unique_destination_path


@pytest.fixture()
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_unique_destination_path_suffixes(tmp_path: Path) -> None:
    base = tmp_path / "cv.pdf"
    base.write_bytes(b"a")

    p1 = unique_destination_path(tmp_path, "cv.pdf")
    assert p1.name == "cv (1).pdf"
    p1.write_bytes(b"b")

    p2 = unique_destination_path(tmp_path, "cv.pdf")
    assert p2.name == "cv (2).pdf"


def test_upload_same_filename_stores_both(client, tmp_path: Path) -> None:
    with patch("dashboard.cv_builder_ui.UPLOADS_DIR", tmp_path):
        res1 = client.post(
            "/api/profile/upload",
            data={
                "upload_type": "cv",
                "file": (BytesIO(b"first"), "resume.pdf"),
            },
            content_type="multipart/form-data",
        )
        assert res1.status_code == 200
        assert res1.get_json()["filename"] == "resume.pdf"

        res2 = client.post(
            "/api/profile/upload",
            data={
                "upload_type": "cv",
                "file": (BytesIO(b"second"), "resume.pdf"),
            },
            content_type="multipart/form-data",
        )
        assert res2.status_code == 200
        assert res2.get_json()["filename"] == "resume (1).pdf"

        assert (tmp_path / "cv" / "resume.pdf").exists()
        assert (tmp_path / "cv" / "resume (1).pdf").exists()
