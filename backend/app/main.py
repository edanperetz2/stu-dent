from fastapi import FastAPI

app = FastAPI(title="Stu-Dent API")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
