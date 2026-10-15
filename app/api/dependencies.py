import hashlib
import hmac
from typing import Annotated

from fastapi import Header, HTTPException, Request, status


async def verify_webhook_signature(
    request: Request,
    x_signature: Annotated[str | None, Header(alias="X-Signature")] = None,
) -> None:
    settings = request.app.state.settings
    request_body = await request.body()

    expected_signature = hmac.new(
        key=settings.webhook_secret.encode("utf-8"),
        msg=request_body,
        digestmod=hashlib.sha256,
    ).hexdigest()

    if x_signature is None or not hmac.compare_digest(x_signature.lower(), expected_signature):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid webhook signature",
        )
