import os
from fastapi import APIRouter, UploadFile, File, BackgroundTasks, Depends, HTTPException
from sqlmodel import Session, select, delete
from app.db.engine import get_session
from app.db.models import Contract, FollowUpMessage
from app.pipeline.runner import run_financial_analysis
from app.pipeline.progress import set_progress, get_progress, clear_progress
from app.config import settings


def get_llm():
    from app.llm.client import GeminiClient
    return GeminiClient()


router = APIRouter(prefix="/contracts", tags=["contracts"])


@router.post("")
def upload(file: UploadFile = File(...), session: Session = Depends(get_session)):
    os.makedirs(settings.upload_dir, exist_ok=True)
    # Sanitize the client-supplied name to a bare basename to avoid path traversal.
    safe_name = os.path.basename(file.filename or "upload")
    dest = os.path.join(settings.upload_dir, safe_name)
    with open(dest, "wb") as f:
        f.write(file.file.read())
    fmt = os.path.splitext(safe_name)[1].lstrip(".").lower()
    c = Contract(filename=safe_name, file_path=dest, format=fmt, status="uploaded")
    session.add(c); session.commit(); session.refresh(c)
    return {"id": c.id, "filename": c.filename, "status": c.status}


def _run_analysis(contract_id: int):
    from app.db.engine import _engine
    with Session(_engine) as session:
        c = session.get(Contract, contract_id)
        c.status = "processing"; session.add(c); session.commit()

        def on_progress(**fields):
            set_progress(contract_id, **fields)

        try:
            result = run_financial_analysis(c.file_path, get_llm(), on_progress=on_progress)
            c.analysis = result.model_dump()
            c.status = "done"
        except Exception as e:  # noqa: BLE001
            c.status = "failed"; c.error = str(e)
        finally:
            clear_progress(contract_id)
        session.add(c); session.commit()


@router.post("/{contract_id}/analyze")
def analyze(contract_id: int, background: BackgroundTasks,
            session: Session = Depends(get_session)):
    c = session.get(Contract, contract_id)
    if not c:
        raise HTTPException(404, "contract not found")
    background.add_task(_run_analysis, contract_id)
    return {"id": contract_id, "status": "processing"}


@router.get("/{contract_id}")
def get_contract(contract_id: int, session: Session = Depends(get_session)):
    c = session.get(Contract, contract_id)
    if not c:
        raise HTTPException(404, "contract not found")
    return {"id": c.id, "filename": c.filename, "status": c.status,
            "error": c.error, "analysis": c.analysis,
            "progress": get_progress(contract_id)}


@router.get("")
def list_contracts(session: Session = Depends(get_session)):
    rows = session.exec(select(Contract)).all()
    out = []
    for c in rows:
        ident = (c.analysis or {}).get("identity") or {}
        out.append({"id": c.id, "filename": c.filename, "status": c.status,
                    "company": ident.get("company"), "period": ident.get("period"),
                    "doc_type": ident.get("doc_type")})
    return out


@router.delete("/{contract_id}")
def delete_contract(contract_id: int, session: Session = Depends(get_session)):
    c = session.get(Contract, contract_id)
    if not c:
        raise HTTPException(404, "document not found")
    # SQLite has no cascade by default; drop the contract's follow-up thread too.
    session.exec(delete(FollowUpMessage).where(FollowUpMessage.contract_id == contract_id))
    session.delete(c); session.commit()
    clear_progress(contract_id)
    return {"id": contract_id, "deleted": True}
