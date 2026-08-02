import uuid
from collections.abc import Generator

from fastapi import HTTPException, status
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

engine = create_engine(settings.database_url, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_or_404[ModelT](
    db: Session, model: type[ModelT], entity_id: uuid.UUID, *, detail: str
) -> ModelT:
    """Fetch by primary key or raise 404 -- for the plain "no extra
    visibility/ownership rule" case (e.g. rooms/equipment). Routes with a
    real authorization rule beyond existence (e.g. appointments, patients)
    should keep their own dedicated lookup instead of forcing it through
    this one.
    """
    entity = db.get(model, entity_id)
    if entity is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)
    return entity
