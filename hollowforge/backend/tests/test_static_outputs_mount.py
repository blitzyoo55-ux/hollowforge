from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import settings
from app.main import create_app


def test_create_app_lightweight_serves_data_outputs_from_data_dir(
    monkeypatch,
    tmp_path,
) -> None:
    data_dir = tmp_path / "data"
    outputs_dir = data_dir / "outputs"
    outputs_dir.mkdir(parents=True, exist_ok=True)
    output_file = outputs_dir / "example-output.png"
    output_file.write_bytes(b"output-bytes")
    monkeypatch.setattr(settings, "DATA_DIR", data_dir)

    with TestClient(create_app(lightweight=True)) as client:
        response = client.get("/data/outputs/example-output.png")

    assert response.status_code == 200
    assert response.content == b"output-bytes"
