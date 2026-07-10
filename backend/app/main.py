from fastapi import FastAPI

from app.api.routes import admin, attending, auth, patients

app = FastAPI(title="Stu-Dent API")

app.include_router(auth.router)
app.include_router(patients.router)
app.include_router(attending.router)
app.include_router(admin.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
