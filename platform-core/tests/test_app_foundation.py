from __future__ import annotations

import pytest

from app.main import create_app


def assert_error_envelope(
    response,
    *,
    expected_status_code: int,
    expected_code: str,
    expected_message: str,
) -> None:
    payload = response.json()

    assert response.status_code == expected_status_code
    assert payload["error"]["code"] == expected_code
    assert payload["error"]["message"] == expected_message
    assert payload["error"]["request_id"] == response.headers["X-Request-Id"]
    assert payload["error"]["correlation_id"] == response.headers["X-Correlation-Id"]


def test_app_wiring_keeps_resolved_settings_on_state(settings) -> None:
    app = create_app(settings=settings)

    assert app.state.settings is settings


@pytest.mark.parametrize(
    ("path", "expected_status_code", "expected_code", "expected_message"),
    [
        ("/test/http/400", 400, "bad_request", "Bad input for test route."),
        ("/test/http/404", 404, "not_found", "Missing test resource."),
    ],
)
def test_http_exception_errors_use_normalized_envelope(
    client,
    path: str,
    expected_status_code: int,
    expected_code: str,
    expected_message: str,
) -> None:
    response = client.get(
        path,
        headers={
            "X-Request-Id": "req-http-test",
            "X-Correlation-Id": "corr-http-test",
        },
    )

    assert_error_envelope(
        response,
        expected_status_code=expected_status_code,
        expected_code=expected_code,
        expected_message=expected_message,
    )
    assert response.json()["error"]["details"] is None


def test_validation_errors_use_normalized_envelope(client) -> None:
    response = client.get(
        "/test/validation",
        params={"limit": 0},
        headers={
            "X-Request-Id": "req-validation-test",
            "X-Correlation-Id": "corr-validation-test",
        },
    )

    assert_error_envelope(
        response,
        expected_status_code=422,
        expected_code="validation_error",
        expected_message="Request validation failed.",
    )
    assert response.json()["error"]["details"]


def test_unhandled_errors_use_normalized_envelope(client) -> None:
    response = client.get("/test/crash")

    assert_error_envelope(
        response,
        expected_status_code=500,
        expected_code="internal_error",
        expected_message="Internal server error.",
    )
    assert response.json()["error"]["details"] is None


def test_request_context_headers_are_available_inside_handlers(client) -> None:
    response = client.get(
        "/test/context",
        headers={
            "X-Request-Id": "req-context-test",
            "X-Correlation-Id": "corr-context-test",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "request_id": "req-context-test",
        "correlation_id": "corr-context-test",
    }
    assert response.headers["X-Request-Id"] == "req-context-test"
    assert response.headers["X-Correlation-Id"] == "corr-context-test"
