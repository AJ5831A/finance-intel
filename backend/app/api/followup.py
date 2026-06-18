from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select
from app.db.engine import get_session
from app.db.models import Contract, FollowUpMessage
from app.pipeline.followup import answer_followup
from app.api.contracts import get_llm

router = APIRouter(prefix="/contracts", tags=["followup"])


class FollowUpRequest(BaseModel):
    question: str


def _serialize(m: FollowUpMessage) -> dict:
    return {"id": m.id, "role": m.role, "content": m.content,
            "created_at": m.created_at.isoformat()}


def _thread(session: Session, contract_id: int) -> list[FollowUpMessage]:
    return session.exec(
        select(FollowUpMessage)
        .where(FollowUpMessage.contract_id == contract_id)
        .order_by(FollowUpMessage.created_at, FollowUpMessage.id)).all()


@router.get("/{contract_id}/followup")
def get_followups(contract_id: int, session: Session = Depends(get_session)):
    if not session.get(Contract, contract_id):
        raise HTTPException(404, "contract not found")
    return {"messages": [_serialize(m) for m in _thread(session, contract_id)]}


@router.post("/{contract_id}/followup")
def post_followup(contract_id: int, req: FollowUpRequest,
                  session: Session = Depends(get_session)):
    c = session.get(Contract, contract_id)
    if not c:
        raise HTTPException(404, "contract not found")
    if c.status != "done":
        raise HTTPException(400, "analysis not complete; nothing to follow up on yet")
    question = req.question.strip()
    if not question:
        raise HTTPException(400, "question must not be empty")

    history = [_serialize(m) for m in _thread(session, contract_id)]
    answer = answer_followup(c.analysis, history, question, get_llm())

    session.add(FollowUpMessage(contract_id=contract_id, role="user", content=question))
    session.add(FollowUpMessage(contract_id=contract_id, role="assistant", content=answer))
    session.commit()

    return {"messages": [_serialize(m) for m in _thread(session, contract_id)]}
