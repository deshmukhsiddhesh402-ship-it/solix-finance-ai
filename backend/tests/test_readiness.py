from unittest.mock import MagicMock, patch


def test_readiness_check_returns_ready_when_database_is_available():
    from app.main import readiness_check

    session = MagicMock()
    with patch("app.main.SessionLocal", return_value=session):
        result = readiness_check()

    session.execute.assert_called_once()
    session.close.assert_called_once()
    assert result["status"] == "ready"
    assert result["database"] == "ok"


def test_readiness_check_returns_503_when_database_is_unavailable():
    from fastapi import HTTPException
    from app.main import readiness_check

    session = MagicMock()
    session.execute.side_effect = RuntimeError("database unavailable")
    with patch("app.main.SessionLocal", return_value=session):
        try:
            readiness_check()
        except HTTPException as exc:
            assert exc.status_code == 503
            assert exc.detail == "Database is not ready."
        else:
            raise AssertionError("readiness_check should fail closed when the database is unavailable")

    session.close.assert_called_once()


def test_security_headers_are_present():
    import asyncio
    from fastapi import Response
    from app.main import security_headers

    async def call_next(_request):
        return Response(content="ok")

    response = asyncio.run(security_headers(object(), call_next))

    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert response.headers["Permissions-Policy"] == "camera=(), microphone=(), geolocation=()"
