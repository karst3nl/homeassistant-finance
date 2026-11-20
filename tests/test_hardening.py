"""Tests für die Härtung: Limits, Header und Ingress-Pfad."""

from __future__ import annotations

from starlette.testclient import TestClient

MAX_CENTS = 10**12


def create_account(client: TestClient) -> dict:
    response = client.post("/api/accounts", json={"name": "Giro", "type": "checking"})
    assert response.status_code == 201, response.text
    return response.json()


def test_uebergrosse_betraege_werden_abgelehnt(client: TestClient) -> None:
    account = create_account(client)
    too_large = MAX_CENTS + 1

    assert (
        client.post(
            "/api/accounts",
            json={"name": "Zu groß", "type": "checking", "initial_balance_cents": too_large},
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/api/transactions",
            json={
                "account_id": account["id"],
                "booking_date": "2026-11-20",
                "amount_cents": too_large,
            },
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/api/transactions",
            json={
                "account_id": account["id"],
                "booking_date": "2026-11-20",
                "amount": "10000000001,00",
            },
        ).status_code
        == 400
    )

    category = client.post("/api/categories", json={"name": "Test", "type": "expense"}).json()
    assert (
        client.post(
            "/api/budgets",
            json={
                "category_id": category["id"],
                "period": "2026-11",
                "limit_cents": too_large,
            },
        ).status_code
        == 400
    )


def test_grosse_requests_werden_abgewiesen(client: TestClient) -> None:
    response = client.post("/api/accounts", content=b"x" * (70 * 1024))

    assert response.status_code == 413
    assert "Payload Too Large" in response.text


def test_grosses_formular_wird_abgewiesen(client: TestClient) -> None:
    response = client.post(
        "/ui/transactions",
        data={"direction": "expense", "description": "x" * (70 * 1024)},
    )

    assert response.status_code == 413


def test_security_header_sind_vorhanden(client: TestClient) -> None:
    response = client.get("/")

    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert "default-src 'self'" in response.headers["content-security-policy"]
    assert "form-action 'self'" in response.headers["content-security-policy"]


def test_boesartiger_ingress_pfad_wird_ignoriert(client: TestClient) -> None:
    for value in (
        "//evil.example",
        "/api/hassio_ingress/tok/../../evil",
        "https://evil.example/",
        "/api\\evil",
    ):
        page = client.get("/", headers={"X-Ingress-Path": value})
        assert '<base href="/" />' in page.text, value

    page = client.get("/", headers={"X-Ingress-Path": "/api/hassio_ingress/tok/"})
    assert '<base href="/api/hassio_ingress/tok/" />' in page.text


def test_suche_ist_laengenbegrenzt(client: TestClient) -> None:
    account = create_account(client)
    client.post(
        "/api/transactions",
        json={
            "account_id": account["id"],
            "booking_date": "2026-11-20",
            "amount_cents": 100,
            "counterparty": "REWE",
        },
    )

    # Der Suchbegriff wird auf 200 Zeichen begrenzt; "rewe" fällt danach weg.
    response = client.get("/ui/transactions", params={"search": "x" * 1000 + "rewe"})

    assert response.status_code == 200
    assert "REWE" not in response.text
