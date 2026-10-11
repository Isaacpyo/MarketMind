"""End-to-end API tests against an in-memory MongoDB (mongomock)."""

from __future__ import annotations

import threading
import time
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from pymongo.errors import ServerSelectionTimeoutError

from marketmind import main as main_module
from marketmind.db import Db
from tests.conftest import auth_header


def test_health_reports_ready_seeded_and_trained(client: TestClient) -> None:
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["ready"] is True
    assert body["seeded"] is True
    assert body["model_version"]


def test_health_survives_a_database_outage(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    def broken(*_: object, **__: object) -> None:
        raise ServerSelectionTimeoutError("no primary")

    monkeypatch.setattr(client.app.state.db.meta, "find_one", broken)  # type: ignore[attr-defined]
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["seeded"] is False


def test_security_headers_and_cors(client: TestClient) -> None:
    response = client.get("/api/health", headers={"Origin": "http://localhost:3000"})
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    evil = client.get("/api/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in evil.headers


# --- auth ------------------------------------------------------------------------------------


def test_register_login_and_me(client: TestClient) -> None:
    payload = {"email": "Grace@Example.com", "password": "a long passphrase", "name": "Grace"}
    created = client.post("/api/auth/register", json=payload)
    assert created.status_code == 201
    assert created.json()["user"] == {
        "id": created.json()["user"]["id"],
        "email": "grace@example.com",
        "name": "Grace",
        "role": "customer",
        "is_demo": False,
    }
    duplicate = client.post("/api/auth/register", json=payload)
    assert duplicate.status_code == 409

    login = client.post(
        "/api/auth/login", json={"email": "grace@example.com", "password": "a long passphrase"}
    )
    assert login.status_code == 200
    me = client.get("/api/auth/me", headers=auth_header(login.json()["access_token"]))
    assert me.json()["email"] == "grace@example.com"


def test_login_rejects_bad_credentials_without_revealing_which(
    client: TestClient, customer_token: str
) -> None:
    wrong_password = client.post("/api/auth/login", json={"email": "ada@example.com", "password": "nope"})
    unknown_user = client.post("/api/auth/login", json={"email": "who@example.com", "password": "nope"})
    assert wrong_password.status_code == unknown_user.status_code == 401
    assert wrong_password.json() == unknown_user.json()


def test_register_validates_input(client: TestClient) -> None:
    bad = client.post("/api/auth/register", json={"email": "not-an-email", "password": "short", "name": ""})
    assert bad.status_code == 422
    fields = {tuple(err["loc"])[-1] for err in bad.json()["detail"]}
    assert fields == {"email", "password", "name"}
    extra = client.post(
        "/api/auth/register",
        json={"email": "x@example.com", "password": "long enough", "name": "X", "role": "admin"},
    )
    assert extra.status_code == 422, "clients must not be able to set their own role"


def test_protected_routes_require_a_valid_token(client: TestClient) -> None:
    assert client.get("/api/cart").status_code == 401
    assert client.get("/api/cart", headers=auth_header("garbage")).status_code == 401
    assert client.get("/api/recommendations/for-you").status_code == 401


def test_demo_login_creates_isolated_shoppers_with_history(client: TestClient, db: Db) -> None:
    first = client.post("/api/auth/demo").json()
    second = client.post("/api/auth/demo").json()
    assert first["user"]["id"] != second["user"]["id"]
    assert first["user"]["is_demo"] is True
    assert first["user"]["role"] == "admin"
    orders = client.get("/api/orders", headers=auth_header(first["access_token"])).json()
    assert len(orders) == 1
    assert orders[0]["lines"][0]["quantity"] == 2
    # Cloned history expires with the shopper and is excluded from training.
    clones = list(db.events.find({"user_id": first["user"]["id"]}))
    assert clones
    assert all(e["source"] == "demo_clone" and e.get("expires_at") for e in clones)


def test_demo_signups_have_a_global_cap(client: TestClient) -> None:
    client.app.state.rate_limiters["demo_global"].limit = 2  # type: ignore[attr-defined]
    codes = [client.post("/api/auth/demo").status_code for _ in range(3)]
    assert codes == [201, 201, 429]


def test_auth_endpoints_are_rate_limited(client: TestClient) -> None:
    client.app.state.rate_limiters["auth"].limit = 2  # type: ignore[attr-defined]
    codes = [
        client.post("/api/auth/login", json={"email": "a@example.com", "password": "x"}).status_code
        for _ in range(3)
    ]
    assert codes == [401, 401, 429]


# --- catalogue -------------------------------------------------------------------------------


def test_list_products_paginates_and_sorts_by_popularity(client: TestClient) -> None:
    page = client.get("/api/products", params={"page_size": 5}).json()
    assert page["total"] == 40
    assert len(page["items"]) == 5
    pops = [p["popularity"] for p in page["items"]]
    assert pops == sorted(pops, reverse=True)
    page2 = client.get("/api/products", params={"page_size": 5, "page": 2}).json()
    assert {p["id"] for p in page["items"]}.isdisjoint({p["id"] for p in page2["items"]})


def test_search_filter_and_price_sort(client: TestClient) -> None:
    results = client.get("/api/products", params={"q": "polkadot mug"}).json()
    assert [p["title"] for p in results["items"]] == ["Blue Polkadot Mug"]
    bags = client.get("/api/products", params={"category": "Bags", "sort": "price_asc"}).json()
    assert bags["total"] == 4
    prices = [p["price"] for p in bags["items"]]
    assert prices == sorted(prices)
    # Regex metacharacters are treated literally.
    assert client.get("/api/products", params={"q": ".*"}).json()["total"] == 0


def test_product_query_validation(client: TestClient) -> None:
    assert client.get("/api/products", params={"page_size": 500}).status_code == 422
    assert client.get("/api/products", params={"sort": "random"}).status_code == 422
    assert client.get("/api/products/not-a-sku").status_code == 422
    assert client.get("/api/products/99999").status_code == 404


def test_categories_and_product_detail(client: TestClient) -> None:
    categories = client.get("/api/categories").json()
    assert sum(c["count"] for c in categories) == 40
    product = client.get("/api/products/10000").json()
    assert product["title"] == "Red Retrospot Mug"


def test_similar_and_also_bought(client: TestClient) -> None:
    similar = client.get("/api/products/10000/similar", params={"limit": 4}).json()
    assert len(similar) == 4
    assert all(item["product"]["id"] != "10000" for item in similar)
    assert {item["source"] for item in similar} == {"content"}
    also = client.get("/api/products/10000/also-bought", params={"limit": 4}).json()
    assert len(also) == 4
    assert {item["source"] for item in also} == {"als"}
    assert also[0]["reason"] == "Often bought by the same shoppers"


# --- events & recommendations ---------------------------------------------------------------


def test_for_you_moves_from_popularity_to_cold_start_to_hybrid(
    client: TestClient, customer_token: str
) -> None:
    headers = auth_header(customer_token)
    feed = client.get("/api/recommendations/for-you", headers=headers).json()
    assert feed["strategy"] == "popularity"
    assert feed["items"][0]["reason"] == "Trending with shoppers right now"

    client.post("/api/events", json={"product_id": "10300", "type": "view"}, headers=headers)
    feed = client.get("/api/recommendations/for-you", headers=headers).json()
    assert feed["strategy"] == "cold_start"
    assert "10300" not in {item["product"]["id"] for item in feed["items"]}
    assert any(item["reason"] == "Because you viewed “Woodland Animal Mug”" for item in feed["items"])

    for sku in ("10301", "10302"):
        client.post("/api/events", json={"product_id": sku, "type": "view"}, headers=headers)
    feed = client.get("/api/recommendations/for-you", headers=headers).json()
    assert feed["strategy"] == "hybrid"
    assert feed["model_version"]
    woodland = [i for i in feed["items"] if i["product"]["title"].startswith("Woodland Animal")]
    assert len(woodland) >= 5


def test_demo_shopper_feed_is_personalised_immediately(client: TestClient, demo_token: str) -> None:
    feed = client.get(
        "/api/recommendations/for-you", params={"limit": 6}, headers=auth_header(demo_token)
    ).json()
    assert feed["strategy"] == "hybrid"
    assert len(feed["items"]) == 6
    assert all(item["reason"] for item in feed["items"])


def test_events_validate_type_and_product(client: TestClient, customer_token: str) -> None:
    headers = auth_header(customer_token)
    forged = client.post("/api/events", json={"product_id": "10000", "type": "purchase"}, headers=headers)
    assert forged.status_code == 422, "purchases can only be recorded by checkout"
    missing = client.post("/api/events", json={"product_id": "99999", "type": "view"}, headers=headers)
    assert missing.status_code == 404
    bad_context = client.post(
        "/api/events", json={"product_id": "10000", "type": "view", "context": "<script>"}, headers=headers
    )
    assert bad_context.status_code == 422


def test_repeated_views_are_deduplicated(client: TestClient, customer_token: str, db: Db) -> None:
    headers = auth_header(customer_token)
    first = client.post("/api/events", json={"product_id": "10000", "type": "view"}, headers=headers).json()
    second = client.post("/api/events", json={"product_id": "10000", "type": "view"}, headers=headers).json()
    assert first == {"accepted": True, "deduplicated": False}
    assert second == {"accepted": True, "deduplicated": True}
    assert db.events.count_documents({"type": "view", "product_id": "10000"}) == 1


def test_trending_by_category(client: TestClient) -> None:
    items = client.get("/api/recommendations/trending", params={"category": "Bags", "limit": 3}).json()
    assert len(items) == 3
    assert {i["product"]["category"] for i in items} == {"Bags"}
    assert items[0]["reason"] == "Popular in Bags"


# --- cart & orders ---------------------------------------------------------------------------


def test_cart_and_checkout_flow(client: TestClient, customer_token: str, db: Db) -> None:
    headers = auth_header(customer_token)
    assert client.get("/api/cart", headers=headers).json() == {"items": [], "item_count": 0, "subtotal": 0.0}
    assert client.post("/api/orders", headers=headers).status_code == 400

    client.post("/api/cart/items", json={"product_id": "10001", "quantity": 2}, headers=headers)
    cart = client.post("/api/cart/items", json={"product_id": "10001"}, headers=headers).json()
    assert cart["items"][0]["quantity"] == 3
    cart = client.post("/api/cart/items", json={"product_id": "10002"}, headers=headers).json()
    assert cart["item_count"] == 4
    cart = client.put("/api/cart/items/10002", json={"quantity": 5}, headers=headers).json()
    assert cart["item_count"] == 8
    cart = client.delete("/api/cart/items/10002", headers=headers).json()
    assert cart["item_count"] == 3
    assert cart["subtotal"] == round(3 * cart["items"][0]["product"]["price"], 2)

    order = client.post("/api/orders", headers=headers)
    assert order.status_code == 201
    body = order.json()
    assert body["total"] == cart["subtotal"]
    assert body["lines"][0]["product_id"] == "10001"
    assert client.get("/api/cart", headers=headers).json()["item_count"] == 0
    assert client.get(f"/api/orders/{body['id']}", headers=headers).json() == body
    assert [o["id"] for o in client.get("/api/orders", headers=headers).json()] == [body["id"]]

    # Server-side signals were recorded for the recommender.
    user_id = client.get("/api/auth/me", headers=headers).json()["id"]
    types = sorted(e["type"] for e in db.events.find({"user_id": user_id}))
    assert types == ["add_to_cart", "add_to_cart", "add_to_cart", "purchase"]


def test_cart_validation(client: TestClient, customer_token: str) -> None:
    headers = auth_header(customer_token)

    def add(body: dict[str, object]) -> int:
        return int(client.post("/api/cart/items", json=body, headers=headers).status_code)

    assert add({"product_id": "10001", "quantity": 0}) == 422
    assert add({"product_id": "10001", "quantity": 99}) == 422
    assert add({"product_id": "99999"}) == 404
    assert client.put("/api/cart/items/10001", json={"quantity": 1}, headers=headers).status_code == 404


def test_orders_are_private(client: TestClient, customer_token: str, demo_token: str) -> None:
    demo_order = client.get("/api/orders", headers=auth_header(demo_token)).json()[0]
    response = client.get(f"/api/orders/{demo_order['id']}", headers=auth_header(customer_token))
    assert response.status_code == 404


# --- admin -----------------------------------------------------------------------------------


def test_admin_requires_admin_role(client: TestClient, customer_token: str) -> None:
    headers = auth_header(customer_token)
    assert client.get("/api/admin/overview", headers=headers).status_code == 403
    assert client.post("/api/admin/retrain", headers=headers).status_code == 403


def test_admin_overview_and_retrain(client: TestClient, demo_token: str) -> None:
    headers = auth_header(demo_token)
    overview = client.get("/api/admin/overview", headers=headers).json()
    assert overview["products"] == 40
    assert overview["model"]["params"]["factors"] == 64
    assert overview["latest_run"]["status"] == "succeeded"
    assert set(overview["latest_run"]["evaluation"]["models"]) == {"popularity", "content", "als", "hybrid"}

    started = client.post(
        "/api/admin/retrain",
        json={"factors": 8, "regularization": 0.1, "alpha": 2.0, "iterations": 5, "hybrid_weight": 0.6},
        headers=headers,
    )
    assert started.status_code == 202
    run_id = started.json()["id"]
    assert started.headers["location"] == f"/api/admin/runs/{run_id}"

    # The run happens on a background thread; wait for it to finish.
    for _ in range(100):
        run = client.get(f"/api/admin/runs/{run_id}", headers=headers).json()
        if run["status"] != "running":
            break
        time.sleep(0.05)
    assert run["status"] == "succeeded"
    assert run["params"]["factors"] == 8
    runs = client.get("/api/admin/runs", headers=headers).json()
    assert runs[0]["id"] == run_id
    assert client.get("/api/health").json()["model_version"] == run_id


def test_retrain_validates_params_and_cooldown(client: TestClient, demo_token: str) -> None:
    headers = auth_header(demo_token)
    assert client.post("/api/admin/retrain", json={"factors": 4096}, headers=headers).status_code == 422
    client.app.state.coordinator.cooldown_seconds = 600  # type: ignore[attr-defined]
    client.app.state.db.training_runs.update_many({}, {"$set": {"trigger": "admin"}})  # type: ignore[attr-defined]
    blocked = client.post("/api/admin/retrain", headers=headers)
    assert blocked.status_code == 429
    assert int(blocked.headers["retry-after"]) > 0


class _NoWaitEvent(threading.Event):
    def wait(self, timeout: float | None = None) -> bool:
        return False


def test_startup_preparation_retries_until_the_database_answers(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[int] = []

    def flaky_prepare(*_args: object) -> None:
        calls.append(1)
        if len(calls) < 3:
            raise ServerSelectionTimeoutError("cluster still waking")

    monkeypatch.setattr(main_module, "prepare", flaky_prepare)
    app = SimpleNamespace(state=SimpleNamespace(db=None, settings=None, engine=None, coordinator=None))
    main_module._prepare_in_background(app, _NoWaitEvent())  # type: ignore[arg-type]
    assert len(calls) == 3
