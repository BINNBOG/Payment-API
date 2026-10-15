import hashlib
import hmac
import json
from uuid import uuid4

import pytest
from httpx import AsyncClient, Response

from app.core.config import Settings


async def get_tariff_id(client: AsyncClient, title: str) -> int:
    response = await client.get("/tariffs")

    assert response.status_code == 200

    tariffs = response.json()
    for tariff in tariffs:
        if tariff["title"] == title:
            return tariff["id"]

    raise AssertionError(f"tariff {title!r} not found")


async def create_card_payment(
    client: AsyncClient,
    tariff_id: int,
    *,
    email: str = "api-test@example.com",
    promo_code: str | None = None,
    idempotency_key: str | None = None,
) -> Response:
    payload: dict[str, object] = {
        "tariff_id": tariff_id,
        "email": email,
        "method": "card",
    }

    if promo_code is not None:
        payload["promo_code"] = promo_code

    headers = {}

    if idempotency_key is not None:
        headers["Idempotency-Key"] = idempotency_key

    return await client.post("/payments", json=payload, headers=headers)


async def send_signed_webhook(
    client: AsyncClient, payload: dict[str, str], secret: str
) -> Response:
    request_body = json.dumps(
        payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")

    signature = hmac.new(
        key=secret.encode("utf-8"),
        msg=request_body,
        digestmod=hashlib.sha256,
    ).hexdigest()

    return await client.post(
        "/webhooks/bank",
        content=request_body,
        headers={
            "Content-Type": "application/json",
            "X-Signature": signature,
        },
    )


async def test_create_payment_without_promo(client: AsyncClient) -> None:
    tariff_id = await get_tariff_id(client, "standard")

    response = await create_card_payment(client, tariff_id)

    assert response.status_code == 201

    payment = response.json()

    assert payment["status"] == "pending"
    assert payment["tariff_id"] == tariff_id
    assert payment["amount"] == 1_990_000
    assert payment["discount"] == 0
    assert payment["method"] == "card"
    assert payment["installment_months"] is None
    assert payment["schedule"] is None


async def test_create_payment_with_lowercase_promo(client: AsyncClient) -> None:
    tariff_id = await get_tariff_id(client, "standard")

    response = await create_card_payment(client, tariff_id, promo_code="kvitto10")

    assert response.status_code == 201

    payment = response.json()

    assert payment["amount"] == 1_791_000
    assert payment["discount"] == 199_000


@pytest.mark.parametrize(
    "months",
    [
        3,
        6,
        12,
    ],
)
async def test_installment_schedule(client: AsyncClient, months: int) -> None:
    tariff_id = await get_tariff_id(client, "premium")

    response = await client.post(
        "/payments",
        json={
            "tariff_id": tariff_id,
            "email": f"installment-{months}@example.com",
            "method": "installment",
            "installment_months": months,
        },
    )

    assert response.status_code == 201

    payment = response.json()
    schedule = payment["schedule"]

    assert payment["installment_months"] == months
    assert len(schedule) == months
    assert sum(schedule) == payment["amount"]
    assert max(schedule) - min(schedule) <= 1
    assert schedule == sorted(schedule, reverse=True)


async def test_idempotency_key_returns_same_payment(client: AsyncClient) -> None:
    tariff_id = await get_tariff_id(client, "basic")
    idempotency_key = f"test-{uuid4()}"

    first_response = await create_card_payment(client, tariff_id, idempotency_key=idempotency_key)

    second_response = await create_card_payment(client, tariff_id, idempotency_key=idempotency_key)

    assert first_response.status_code == 201
    assert second_response.status_code == 200

    first_payment = first_response.json()
    second_payment = second_response.json()

    assert second_payment == first_payment
    assert second_payment["id"] == first_payment["id"]


async def test_invalid_transition_does_not_change_status(
    client: AsyncClient, settings: Settings
) -> None:
    tariff_id = await get_tariff_id(client, "basic")

    create_response = await create_card_payment(client, tariff_id)

    assert create_response.status_code == 201

    payment_id = create_response.json()["id"]

    success_response = await send_signed_webhook(
        client=client,
        payload={
            "payment_id": payment_id,
            "status": "succeeded",
        },
        secret=settings.webhook_secret,
    )

    assert success_response.status_code == 200
    assert success_response.json() == {"result": "ok"}

    invalid_response = await send_signed_webhook(
        client=client,
        payload={
            "payment_id": payment_id,
            "status": "failed",
        },
        secret=settings.webhook_secret,
    )

    assert invalid_response.status_code == 409
    assert invalid_response.json() == {"error": "invalid_transition"}

    get_response = await client.get(f"/payments/{payment_id}")

    assert get_response.status_code == 200
    assert get_response.json()["status"] == "succeeded"


async def test_invalid_webhook_signature_returns_401(client: AsyncClient) -> None:
    tariff_id = await get_tariff_id(client, "basic")

    create_response = await create_card_payment(client, tariff_id)

    assert create_response.status_code == 201

    payment_id = create_response.json()["id"]

    webhook_response = await client.post(
        "/webhooks/bank",
        json={
            "payment_id": payment_id,
            "status": "succeeded",
        },
        headers={
            "X-Signature": "incorrect-signature",
        },
    )

    assert webhook_response.status_code == 401
    assert webhook_response.json() == {"detail": "invalid webhook signature"}

    get_response = await client.get(f"/payments/{payment_id}")

    assert get_response.status_code == 200
    assert get_response.json()["status"] == "pending"


async def test_get_payments_filters(client: AsyncClient, settings: Settings) -> None:
    tariff_id = await get_tariff_id(client, "basic")

    unique_email = f"filter-{uuid4().hex}@example.com"

    create_response = await create_card_payment(client, tariff_id, email=unique_email)

    assert create_response.status_code == 201

    payment_id = create_response.json()["id"]

    email_response = await client.get(
        "/payments",
        params={
            "email": unique_email,
        },
    )

    assert email_response.status_code == 200
    assert len(email_response.json()) == 1
    assert email_response.json()[0]["id"] == payment_id

    pending_response = await client.get(
        "/payments",
        params={
            "email": unique_email,
            "status": "pending",
        },
    )

    assert pending_response.status_code == 200
    assert len(pending_response.json()) == 1
    assert pending_response.json()[0]["id"] == payment_id

    succeeded_before_webhook = await client.get(
        "/payments",
        params={
            "email": unique_email,
            "status": "succeeded",
        },
    )

    assert succeeded_before_webhook.status_code == 200
    assert succeeded_before_webhook.json() == []

    webhook_response = await send_signed_webhook(
        client=client,
        payload={
            "payment_id": payment_id,
            "status": "succeeded",
        },
        secret=settings.webhook_secret,
    )

    assert webhook_response.status_code == 200

    succeeded_after_webhook = await client.get(
        "/payments",
        params={
            "email": unique_email,
            "status": "succeeded",
        },
    )

    assert succeeded_after_webhook.status_code == 200
    assert len(succeeded_after_webhook.json()) == 1
    assert succeeded_after_webhook.json()[0]["id"] == payment_id


async def test_get_missing_payment_returns_404(client: AsyncClient) -> None:
    missing_id = uuid4()
    response = await client.get(f"/payments/{missing_id}")

    assert response.status_code == 404
    assert response.json() == {"detail": "payment not found"}


async def test_unknown_promo_returns_422(client: AsyncClient) -> None:
    tariff_id = await get_tariff_id(client, "basic")
    response = await create_card_payment(client, tariff_id, promo_code="UNKNOWN")

    assert response.status_code == 422
