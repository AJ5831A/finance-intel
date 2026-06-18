from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, select
from app.db.engine import init_db
from app.db.models import Contract
from app.api import contracts, compare, followup


def _reset_stale():
    """Any row left mid-flight by a server restart is marked failed, so a reload
    never leaves a 'processing'/'uploaded' zombie that can never complete."""
    from app.db import engine as engine_mod
    with Session(engine_mod._engine) as session:
        stale = session.exec(
            select(Contract).where(Contract.status.in_(["processing", "uploaded"]))).all()
        for c in stale:
            c.status = "failed"
            c.error = "Interrupted by a server restart."
            session.add(c)
        if stale:
            session.commit()


def create_app() -> FastAPI:
    app = FastAPI(title="Ledger — Financial Document Analyst")
    app.add_middleware(CORSMiddleware, allow_origins=["*"],
                       allow_methods=["*"], allow_headers=["*"])

    @app.on_event("startup")
    def _startup():
        init_db()
        _reset_stale()

    app.include_router(contracts.router)
    app.include_router(compare.router)
    app.include_router(followup.router)
    return app


app = create_app()
