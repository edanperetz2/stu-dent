import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import (
    admin,
    appointments,
    attending,
    auth,
    equipment,
    forum,
    messages,
    notifications,
    patients,
    reports,
    resources,
    rooms,
    scheduling_assistant,
    students,
    waitlist,
    websocket,
)
from app.config import settings
from app.realtime.listener import listen_forever


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    listener_task = asyncio.create_task(listen_forever())
    try:
        yield
    finally:
        listener_task.cancel()
        try:
            await listener_task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="Stu-Dent API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.frontend_origin_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(patients.router)
app.include_router(attending.router)
app.include_router(admin.router)
app.include_router(rooms.router)
app.include_router(resources.router)
app.include_router(students.router)
app.include_router(equipment.router)
app.include_router(appointments.router)
app.include_router(notifications.router)
app.include_router(waitlist.router)
app.include_router(forum.router)
app.include_router(messages.router)
app.include_router(scheduling_assistant.router)
app.include_router(reports.router)
app.include_router(websocket.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
