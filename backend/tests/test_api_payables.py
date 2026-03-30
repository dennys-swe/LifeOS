from datetime import date

from app.models.payable import PayableStatus


def test_create_payable(client):
    payload = {
        "title": "Aluguel",
        "amount": 1200.0,
        "due_date": str(date.today()),
        "status": "PENDING",
        "payment_date": None,
    }

    response = client.post("/payables", json=payload)

    assert response.status_code == 201
    data = response.json()
    assert data["id"]
    assert data["title"] == payload["title"]
    assert data["status"] == "PENDING"


def test_pay_payable_updates_status(client):
    payload = {
        "title": "Internet",
        "amount": 120.0,
        "due_date": str(date.today()),
        "status": "PENDING",
        "payment_date": None,
    }

    create_response = client.post("/payables", json=payload)
    payable_id = create_response.json()["id"]

    pay_response = client.patch(f"/payables/{payable_id}/pay")

    assert pay_response.status_code == 200
    data = pay_response.json()
    assert data["status"] == PayableStatus.PAID.value
    assert data["payment_date"] == str(date.today())


def test_delete_payable_removes_from_list(client):
    payload = {
        "title": "Luz",
        "amount": 220.0,
        "due_date": str(date.today()),
        "status": "PENDING",
        "payment_date": None,
    }

    create_response = client.post("/payables", json=payload)
    payable_id = create_response.json()["id"]

    delete_response = client.delete(f"/payables/{payable_id}")
    assert delete_response.status_code == 204

    list_response = client.get("/payables")
    ids = [item["id"] for item in list_response.json()]
    assert payable_id not in ids


def test_pay_nonexistent_payable_returns_404(client):
    response = client.patch("/payables/00000000-0000-0000-0000-000000000000/pay")
    assert response.status_code == 404
    data = response.json()
    assert "detail" in data