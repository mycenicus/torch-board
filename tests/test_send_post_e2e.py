"""Spawn application process and send requests"""

import subprocess
import time
from typing import Any

import pytest
import requests

from board.telemetry.protocol import TelemetryMessage, TelemetrySource

url = "http://127.0.0.1:8000/api/v1/telemetry"


@pytest.fixture
def source() -> TelemetrySource:
    return TelemetrySource(
        machine_id="training-node-01",
        hostname="gpu-server-01",
        software_version="0.1.0",
    )


@pytest.fixture
def message_data(source: TelemetrySource) -> dict[str, Any]:
    return {
        "source": source.model_dump(),
        "sequence": 1,
        "event_type": "metrics.batch",
        "payload": {
            "metrics": [
                {
                    "name": "loss",
                    "value": 0.42,
                    "unit": None,
                    "tags": {"split": "train"},
                }
            ]
        },
    }


@pytest.fixture
def message(message_data: dict[str, Any]) -> TelemetryMessage:
    return TelemetryMessage.model_validate(message_data)


def test_telemetry_server_accepts_message(message: TelemetryMessage):
    port = 8000

    server = subprocess.Popen(
        [
            "uv",
            "run",
            "uvicorn",
            "board.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--app-dir",
            "src",
        ]
    )

    try:
        url = f"http://127.0.0.1:{port}"

        # wait for the server to become ready
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            try:
                response = requests.get(url=url, timeout=1)
                if response.status_code == 200:
                    break
            except requests.ConnectionError:
                pass

            time.sleep(0.1)
        else:
            raise AssertionError("Server did not start")

        # Send the actual telemetry
        response = requests.post(
            f"{url}/api/v1/telemetry", json=message.model_dump(mode="json"), timeout=5
        )

        assert response.status_code == 202

    finally:
        server.terminate()

        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait()
