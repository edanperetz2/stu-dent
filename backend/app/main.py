from fastapi import FastAPI

from app.api.routes import auth

app = FastAPI(title="Stu-Dent API")

app.include_router(auth.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
