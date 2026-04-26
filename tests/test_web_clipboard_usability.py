"""Regression tests for business-user clipboard/sample workflow handling."""

import web.app as web_app


app = web_app.app


def test_clipboard_preserves_full_user_login_sample():
    sample = web_app.SAMPLE_WORKFLOWS["user-login"]["text"]

    with app.test_client() as client:
        response = client.post("/api/clipboard", json={"text": sample})

    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert "1. User opens login page" in data["workflow_text"]
    assert "5. If 2FA enabled, send verification code" in data["workflow_text"]
    assert "9. End" in data["workflow_text"]
    assert data["summary"]["step_count"] == 9
    assert data["summary"]["numbered_steps"] == 9
    assert data["summary"]["decision_count"] == 5
    assert data["summary"]["decision_steps"] == 5
