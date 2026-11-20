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
    assert "nav a.active" in response.text


def test_aktiver_menupunkt_wird_markiert(client: TestClient) -> None:
    pages = {
        "/": "Übersicht",
        "/ui/transactions": "Buchungen",
        "/ui/budgets": "Budgets",
        "/ui/recurring": "Fixkosten",
        "/ui/reports": "Auswertungen",
        "/ui/accounts": "Konten",
        "/ui/categories": "Kategorien",
        "/ui/salary": "Monatsgehalt",
        "/ui/backups": "Backups",
    }
    for path, label in pages.items():
        page = client.get(path)
        assert page.status_code == 200, path
        assert page.text.count('aria-current="page"') == 1, path
        assert f'class="active" aria-current="page">{label}</a>' in page.text, path

    ingress_page = client.get(
        "/ui/accounts", headers={"X-Ingress-Path": "/api/hassio_ingress/tok/"}
    )
    assert 'class="active" aria-current="page">Konten</a>' in ingress_page.text


def test_aktiver_menupunkt_auf_bearbeitungsseiten(client: TestClient) -> None:
    create_account(client)
    create_expense(client)

    for path, label in (
        ("/ui/accounts/1/edit", "Konten"),
        ("/ui/transactions/1/edit", "Buchungen"),
    ):
        page = client.get(path)
        assert page.status_code == 200, path
        assert page.text.count('aria-current="page"') == 1, path
        assert f'class="active" aria-current="page">{label}</a>' in page.text, path


def test_konto_bearbeiten_ueber_ui(client: TestClient) -> None:
    create_account(client)
    edit_page = client.get("/ui/accounts/1/edit")
    assert edit_page.status_code == 200
    assert 'value="Giro"' in edit_page.text
    assert 'value="100,00"' in edit_page.text

    response = client.post(
        "/ui/accounts/1",
        data={
            "name": "Giro neu",
            "type": "savings",
            "currency": "EUR",
            "initial_balance": "250,00",
            "active": "1",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    accounts = client.get("/ui/accounts").text
    assert "Giro neu" in accounts
    assert "Sparkonto" in accounts
    assert "250,00 EUR" in accounts
    assert "100,00 EUR" not in accounts


def test_buchung_bearbeiten_ueber_ui(client: TestClient) -> None:
    create_account(client)
    client.post("/ui/categories", data={"name": "Lebensmittel", "type": "expense"})
    create_expense(client, category_id="1")

    edit_page = client.get("/ui/transactions/1/edit")
    assert edit_page.status_code == 200
    assert 'value="12,34"' in edit_page.text
    assert 'value="REWE"' in edit_page.text

    response = client.post(
        "/ui/transactions/1",
        data={
            "direction": "income",
            "booking_date": "2026-11-20",
            "account_id": "1",
            "amount": "20,00",
            "counterparty": "Erstattung",
            "category_id": "",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    page = client.get("/ui/transactions").text
    assert "Erstattung" in page
    assert "REWE" not in page
    assert "20,00 EUR" in page
    assert "120,00 EUR" in client.get("/").text


def test_fixkosten_ueber_ui(client: TestClient) -> None:
    create_account(client)
    client.post("/ui/categories", data={"name": "Wohnen", "type": "expense"})

    page = client.get("/ui/recurring")
    assert "Noch keine Regeln vorhanden" in page.text
    assert 'href="ui/recurring"' in client.get("/").text

    today = client.get("/ui/recurring").text
    assert "Neue Regel" in today

    response = client.post(
        "/ui/recurring",
        data={
            "name": "Miete",
            "direction": "expense",
            "interval": "monthly",
            "amount": "900,00",
            "account_id": "1",
            "category_id": "1",
            "start_date": "2026-11-01",
            "counterparty": "Vermieter",
            "active": "1",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    page = client.get("/ui/recurring").text
    assert "Miete" in page
    assert "900,00 EUR" in page
    assert "Monatlich" in page
    assert "Vermieter" in page
    assert "automatisch (Fixkosten)" in client.get("/ui/transactions").text

    edit_page = client.get("/ui/recurring/1/edit")
    assert edit_page.status_code == 200
    assert 'value="900,00"' in edit_page.text

    response = client.post(
        "/ui/recurring/1",
        data={
            "name": "Miete neu",
            "direction": "expense",
            "interval": "yearly",
            "amount": "10.800,00",
            "account_id": "1",
            "category_id": "1",
            "start_date": "2026-11-01",
            "active": "1",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    assert "Miete neu" in client.get("/ui/recurring").text
    assert "Jährlich" in client.get("/ui/recurring").text

    response = client.post("/ui/recurring/1/delete", follow_redirects=False)
    assert response.status_code == 303
    assert "Noch keine Regeln vorhanden" in client.get("/ui/recurring").text
    assert "Vermieter" in client.get("/ui/transactions").text
