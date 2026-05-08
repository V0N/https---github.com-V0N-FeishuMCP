import asyncio
import json
import logging

from fastapi import APIRouter, BackgroundTasks, Request
from fastapi.responses import JSONResponse

from app.config.settings import settings
from app.utils.crypto import DecryptError, decrypt_feishu_event

logger = logging.getLogger(__name__)

router = APIRouter()


async def process_message_event(event_data: dict):
    from app.service.message_handler import message_handler
    if message_handler is not None:
        await message_handler.handle_message(event_data)


@router.post("/webhook/lark/event")
async def lark_event(request: Request, background_tasks: BackgroundTasks):
    raw_body = await request.body()
    body_str = raw_body.decode("utf-8")
    data = json.loads(body_str)

    if "encrypt" in data:
        try:
            encrypt_key = settings.FEISHU_ENCRYPT_KEY if settings else ""
            event_data = decrypt_feishu_event(data["encrypt"], encrypt_key)
        except DecryptError:
            return JSONResponse(status_code=400, content={"code": 400, "msg": "decrypt failed"})
    else:
        event_data = data

    if "challenge" in event_data:
        return {"challenge": event_data["challenge"]}

    header = event_data.get("header", {})
    event = event_data.get("event", {})

    event_type = header.get("event_type") or event.get("type", "")

    if event_type == "im.message.receive_v1":
        background_tasks.add_task(_run_process_message_event, event_data)
        return JSONResponse(status_code=200, content={})

    return JSONResponse(status_code=200, content={})


def _run_process_message_event(event_data: dict):
    asyncio.run(process_message_event(event_data))
