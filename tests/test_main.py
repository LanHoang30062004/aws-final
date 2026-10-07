from fastapi.testclient import TestClient

from main import create_app


def test_health():
    with TestClient(create_app("sqlite://")) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_item_crud():
    with TestClient(create_app("sqlite://")) as client:
        created = client.post(
            "/items",
            json={"name": "Notebook", "description": "Project notes"},
        )
        assert created.status_code == 201
        item = created.json()
        assert item["name"] == "Notebook"
        assert item["description"] == "Project notes"

        assert client.get("/items").json() == [item]
        assert client.get(f"/items/{item['id']}").json() == item
        assert client.delete(f"/items/{item['id']}").status_code == 204
        assert client.get(f"/items/{item['id']}").status_code == 404


def test_create_item_validates_name():
    with TestClient(create_app("sqlite://")) as client:
        response = client.post("/items", json={"name": ""})

    assert response.status_code == 422
