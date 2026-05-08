import logging
import json
import sys
import time

from fastapi import FastAPI
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.api.webhook import router as webhook_router
from app.config.settings import settings


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        msg = record.getMessage()
        try:
            parsed = json.loads(msg)
            if isinstance(parsed, dict):
                return msg
        except (ValueError, TypeError):
            pass
        return json.dumps(
            {
                "time": self.formatTime(record, self.datefmt),
                "level": record.levelname,
                "name": record.name,
                "message": msg,
            },
            ensure_ascii=False,
        )


_handler = logging.StreamHandler(sys.stdout)
_handler.setFormatter(_JsonFormatter())
logging.root.handlers = [_handler]
logging.root.setLevel(
    getattr(logging, settings.LOG_LEVEL if settings else "INFO", logging.INFO)
)

app = FastAPI()

app.include_router(webhook_router)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.on_event("startup")
async def startup():
    from app.service.directory_service import directory_service
    from app.service.attendance_service import AttendanceService, attendance_service
    from app.service.message_service import message_service
    from app.service.session_service import SessionService
    from app.service.message_handler import MessageHandler
    import app.service.message_handler as handler_module

    await attendance_service.initialize()
    await directory_service.sync_all()

    handler_module.message_handler = MessageHandler(
        directory_service=directory_service,
        attendance_service=attendance_service,
        message_service=message_service,
        session_service=SessionService(),
    )

    scheduler = AsyncIOScheduler()
    scheduler.add_job(directory_service.sync_all, "interval", seconds=3600)
    scheduler.start()
