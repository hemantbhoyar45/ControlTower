from fastapi import APIRouter, Header, HTTPException, Request, status

from ..config import telegram_webhook_secret

router = APIRouter(prefix="/api/telegram", tags=["telegram"])


@router.post("/webhook", status_code=status.HTTP_200_OK)
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> dict[str, bool]:
    expected_secret = telegram_webhook_secret()
    if expected_secret and x_telegram_bot_api_secret_token != expected_secret:
        raise HTTPException(status_code=403, detail="Invalid Telegram secret token.")

    telegram_service = getattr(request.app.state, "telegram_service", None)
    if not telegram_service or not telegram_service.application:
        raise HTTPException(status_code=503, detail="Telegram service is not active.")

    payload = await request.json()
    await telegram_service.process_update(payload)
    return {"ok": True}
