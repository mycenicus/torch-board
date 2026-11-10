from fastapi.testclient import TestClient

from board.main import app


def valid_message():
    return {
        "sequence": 1,
        "event_type": "metrics.batch",
        "source": {
            "machine_id": "training-node-01",
            "hostname": "gpu-server-01",
            "software_version": "0.1.0",
        },
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


def test_receive_telemetry():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/telemetry",
            json=valid_message(),
        )

        assert response.status_code == 202
        assert response.json()["status"] == "accepted"
        assert "message_id" in response.json()


def test_invalid_telemetry_envelope():
    payload = valid_message()
    payload["sequence"] = -1

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/telemetry",
            json=payload,
        )

        assert response.status_code == 422


def test_invalid_event_payload():
    payload = valid_message()
    payload["payload"] = {"metrics": [{"value": 0.42}]}

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/telemetry",
            json=payload,
        )

        assert response.status_code == 422


def test_telemetry_status():
    with TestClient(app) as client:
        response = client.get("/api/v1/telemetry/status")

        assert response.status_code == 200

        data = response.json()

        assert data["worker_running"] is True
        assert data["queue_capacity"] == 1000
        assert data["queue_size"] == 0
