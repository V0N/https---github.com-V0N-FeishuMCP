import json
import logging

logger = logging.getLogger(__name__)


class MessageService:
    def __init__(self, client):
        self._client = client

    async def send_text(self, open_id: str, text: str) -> None:
        try:
            await self._client.request(
                "POST",
                "/im/v1/messages",
                params={"receive_id_type": "open_id"},
                json={
                    "receive_id": open_id,
                    "msg_type": "text",
                    "content": json.dumps({"text": text}),
                },
            )
        except Exception as e:
            logger.error("发送文本消息失败，open_id=%s: %s", open_id, e)

    async def send_card(self, open_id: str, card: dict) -> None:
        try:
            await self._client.request(
                "POST",
                "/im/v1/messages",
                params={"receive_id_type": "open_id"},
                json={
                    "receive_id": open_id,
                    "msg_type": "interactive",
                    "content": json.dumps(card),
                },
            )
        except Exception as e:
            logger.error("发送卡片消息失败，open_id=%s: %s", open_id, e)


from app.utils.feishu_client import feishu_client
message_service = MessageService(feishu_client)
