"""Tests für das servergerenderte Dashboard und die Eingabeformulare."""

from __future__ import annotations

from starlette.testclient import TestClient


def create_account(client: TestClient, name: str = "Giro", initial: str = "100,00") -> None:
    response = client.post(
        "/ui/accounts",
        data={"name": name, "type": "checking", "currency": "EUR", "initial_balance": initial},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text


def create_expense(client: TestClient, amount: str = "12,34", **extra: object) -> None:
    payload = {
        "direction": "expense",
        "booking_date": "2026-11-19",
        "account_id": "1",
        "amount": amount,
        "counterparty": "REWE",
        **extra,
    }
    response = client.post("/ui/transactions", data=payload, follow_redirects=False)
    assert response.status_code == 303, response.text


def test_dashboard_leer(client: TestClient) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert "Saldo gesamt" in response.text
    assert "Noch keine Konten vorhanden" in response.text
    assert "Noch keine Buchungen vorhanden" in response.text


def test_konto_und_ausgabe_ueber_ui(client: TestClient) -> None:
    create_account(client)
    dashboard = client.get("/")
    assert "100,00 EUR" in dashboard.text

    client.post(
        "/ui/categories", data={"name": "Lebensmittel", "type": "expense"}, follow_redirects=False
    )
    create_expense(client, category_id="1")

    dashboard = client.get("/")
    assert "-12,34 EUR" in dashboard.text
    assert "87,66 EUR" in dashboard.text
    assert "REWE" in dashboard.text
    assert "Lebensmittel" in dashboard.text


def test_einnahme_erhoeht_saldo(client: TestClient) -> None:
    create_account(client)
    response = client.post(
        "/ui/transactions",
        data={
            "direction": "income",
            "booking_date": "2026-11-19",
            "account_id": "1",
            "amount": "50,00",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert "150,00 EUR" in client.get("/").text


def test_ungueltige_eingabe_zeigt_fehler(client: TestClient) -> None:
    create_account(client)
    response = client.post(
        "/ui/transactions",
        data={
            "direction": "expense",
            "booking_date": "2026-11-19",
            "account_id": "1",
            "amount": "abc",
        },
    )

    assert response.status_code == 400
    assert "Bitte einen gültigen Betrag angeben" in response.text


def test_buchungen_seite_und_suche(client: TestClient) -> None:
    create_account(client)
    create_expense(client)

    assert "REWE" in client.get("/ui/transactions").text
    assert "REWE" in client.get("/ui/transactions?search=rewe").text
    assert "REWE" not in client.get("/ui/transactions?search=unknown").text


def test_loeschen_ueber_ui(client: TestClient) -> None:
    create_account(client)
    create_expense(client)

    response = client.post("/ui/transactions/1/delete", follow_redirects=False)
    assert response.status_code == 303
    assert "REWE" not in client.get("/").text


def test_konto_mit_buchungen_kann_nicht_geloescht_werden(client: TestClient) -> None:
    create_account(client)
    create_expense(client)

    response = client.post("/ui/accounts/1/delete")
    assert response.status_code == 409
    assert "solange Buchungen darauf existieren" in response.text


def test_ingress_pfad_wird_fuer_links_und_redirects_genutzt(client: TestClient) -> None:
    headers = {"X-Ingress-Path": "/api/hassio_ingress/tok/"}
    page = client.get("/", headers=headers)
    assert '<base href="/api/hassio_ingress/tok/" />' in page.text

    response = client.post(
        "/ui/accounts",
        data={"name": "Giro", "type": "checking", "initial_balance": "0"},
        headers=headers,
        follow_redirects=False,
    )
    assert response.headers["location"] == "/api/hassio_ingress/tok/ui/accounts"


def test_stylesheet_wird_ausgeliefert(client: TestClient) -> None:
    response = client.get("/static/style.css")

    assert response.status_code == 200
    assert "color-scheme" in response.text
