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
)

app = FastAPI(title="Stu-Dent API")

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


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
