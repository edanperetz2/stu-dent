import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import (
    admin,
    appointments,
    attending,
    auth,
    availability,
    direct_messages,
    equipment,
    forum,
    notifications,
    patients,
    rooms,
    waitlist,
    websocket,
)
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

app.include_router(auth.router)
app.include_router(patients.router)
app.include_router(attending.router)
app.include_router(admin.router)
app.include_router(rooms.router)
app.include_router(equipment.router)
app.include_router(appointments.router)
app.include_router(availability.router)
app.include_router(notifications.router)
app.include_router(waitlist.router)
app.include_router(forum.router)
app.include_router(direct_messages.router)
app.include_router(websocket.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
