from fastapi.testclient import TestClient

from tests.conftest import auth_header


def test_registro_crea_empresa_y_pipeline(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "company_name": "Norte Software",
            "name": "Ana Ruiz",
            "email": "ana@example.com",
            "password": "secreto123",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["user"]["role"] == "owner"
    assert body["tenant"]["name"] == "Norte Software"
    assert body["access_token"]

    pipelines = client.get("/api/v1/pipelines", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert pipelines.status_code == 200
    stages = pipelines.json()[0]["stages"]
    assert [stage["name"] for stage in stages] == [
        "Nuevo",
        "Calificación",
        "Propuesta",
        "Negociación",
        "Ganada",
        "Perdida",
    ]


def test_sin_token_responde_401(client: TestClient) -> None:
    response = client.get("/api/v1/accounts")
    assert response.status_code == 401


def test_aislamiento_entre_empresas(client: TestClient) -> None:
    owner = auth_header(client, "Norte", "ana@example.com")
    other = auth_header(client, "Sur", "luis@example.com")

    created = client.post("/api/v1/accounts", headers=owner, json={"name": "Cliente Norte"})
    assert created.status_code == 201
    account_id = created.json()["id"]

    hidden = client.get(f"/api/v1/accounts/{account_id}", headers=other)
    assert hidden.status_code == 404
    listed = client.get("/api/v1/accounts", headers=other)
    assert listed.json() == []


def test_visor_no_puede_escribir(client: TestClient) -> None:
    owner = auth_header(client, "Norte", "ana@example.com")
    created = client.post(
        "/api/v1/users",
        headers=owner,
        json={"name": "Vera", "email": "vera@example.com", "password": "secreto123", "role": "viewer"},
    )
    assert created.status_code == 201
    login = client.post("/api/v1/auth/login", json={"email": "vera@example.com", "password": "secreto123"})
    viewer = {"Authorization": f"Bearer {login.json()['access_token']}"}

    denied = client.post("/api/v1/accounts", headers=viewer, json={"name": "No permitido"})
    assert denied.status_code == 403
    readable = client.get("/api/v1/accounts", headers=viewer)
    assert readable.status_code == 200


def test_cotizacion_calcula_totales_en_el_servidor(client: TestClient) -> None:
    headers = auth_header(client, "Norte", "ana@example.com")
    account = client.post("/api/v1/accounts", headers=headers, json={"name": "Acme"})
    product = client.post(
        "/api/v1/products",
        headers=headers,
        json={"name": "Implementación", "code": "IMP", "unit_price": "100.00", "currency": "USD", "is_service": True},
    )
    quote = client.post(
        "/api/v1/quotes",
        headers=headers,
        json={
            "account_id": account.json()["id"],
            "currency": "USD",
            "items": [
                {
                    "product_id": product.json()["id"],
                    "quantity": "2",
                    "unit_price": "1.00",
                    "discount": "10.00",
                }
            ],
        },
    )
    assert quote.status_code == 201
    body = quote.json()
    assert body["items"][0]["unit_price"] == "100.00"
    assert body["subtotal"] == "200.00"
    assert body["total"] == "190.00"


def test_etapa_de_otro_pipeline_se_rechaza(client: TestClient) -> None:
    headers = auth_header(client, "Norte", "ana@example.com")
    pipelines = client.get("/api/v1/pipelines", headers=headers).json()
    default_id = pipelines[0]["id"]
    other = client.post("/api/v1/pipelines", headers=headers, json={"name": "Alianzas"})
    stage = client.post(
        f"/api/v1/pipelines/{other.json()['id']}/stages",
        headers=headers,
        json={"name": "Contacto", "probability": 20, "outcome": "open"},
    )
    opportunity = client.post(
        "/api/v1/opportunities",
        headers=headers,
        json={"title": "Licencia anual", "amount": "5000", "pipeline_id": default_id},
    )
    moved = client.post(
        f"/api/v1/opportunities/{opportunity.json()['id']}/stage",
        headers=headers,
        json={"stage_id": stage.json()["id"]},
    )
    assert moved.status_code == 409


def test_clave_de_campo_personalizado_es_unica_por_empresa(client: TestClient) -> None:
    first = auth_header(client, "Norte", "ana@example.com")
    second = auth_header(client, "Sur", "luis@example.com")
    payload = {
        "entity_type": "account",
        "label": "Sector",
        "key": "sector",
        "field_type": "text",
    }
    assert client.post("/api/v1/custom-fields", headers=first, json=payload).status_code == 201
    assert client.post("/api/v1/custom-fields", headers=first, json=payload).status_code == 409
    assert client.post("/api/v1/custom-fields", headers=second, json=payload).status_code == 201


def test_convertir_prospecto_abre_oportunidad(client: TestClient) -> None:
    headers = auth_header(client, "Norte", "ana@example.com")
    lead = client.post("/api/v1/leads", headers=headers, json={"title": "Proyecto portal", "status": "qualified"})
    converted = client.post(f"/api/v1/leads/{lead.json()['id']}/convert", headers=headers)
    assert converted.status_code == 201
    assert converted.json()["status"] == "open"
    assert converted.json()["lead_id"] == lead.json()["id"]

    panel = client.get("/api/v1/dashboard", headers=headers)
    assert panel.status_code == 200
    assert panel.json()["open_opportunities"] == 1
    assert panel.json()["open_leads"] == 0
