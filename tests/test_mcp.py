from fastapi.testclient import TestClient

from server.main import app


client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "running"


def test_mcp_tools_list():
    response = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["result"]["tools"][0]["name"] == "verify_output"


def test_verify_rejects_short_content():
    response = client.post("/verify", json={"content": "short"})
    assert response.status_code == 400
