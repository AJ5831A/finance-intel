import io
import pytest
from fastapi.testclient import TestClient
import app.api.contracts as contracts_mod
import app.api.followup as followup_mod
from app.main import create_app
from app.db.engine import init_db, make_engine
from app.schemas.models import StructuredDocument
from app.schemas.financial import (
    FinancialAnalysis, DocumentIdentity, Metric, ToneAnalysis, RiskFactor, InvestmentMemo)
from app.pipeline.followup import _build_context, answer_followup


def _fake_analysis():
    return FinancialAnalysis(
        identity=DocumentIdentity(company="Intel", period="Q4 2024", doc_type="earnings release"),
        structure=StructuredDocument(title="Intel Q4", blocks=[]),
        metrics=[Metric(name="revenue", value="$14.3B", period="Q4 2024")],
        tone=ToneAnalysis(overall_sentiment="cautious", confidence_score=40, summary="Guarded."),
        risk_factors=[RiskFactor(category="market", title="Demand", text="Soft PC demand.",
                                 severity=60)],
        memo=InvestmentMemo(company_overview="Chipmaker.", financial_summary="Revenue $14.3B.",
                            bull_case=["share gains"], bear_case=["margin pressure"]))


# --- context builder (pure) ---

def test_build_context_includes_findings():
    ctx = _build_context(_fake_analysis().model_dump())
    assert "Intel" in ctx
    assert "revenue" in ctx and "$14.3B" in ctx
    assert "cautious" in ctx
    assert "Demand" in ctx and "Soft PC demand." in ctx
    assert "share gains" in ctx and "margin pressure" in ctx


def test_build_context_tolerates_empty():
    assert isinstance(_build_context({}), str)
    assert isinstance(_build_context(None), str)


def test_answer_followup_threads_history(mock_llm):
    mock_llm.queue_text("Because PC demand softened.")
    history = [{"role": "user", "content": "What was revenue?"},
               {"role": "assistant", "content": "$14.3B."}]
    out = answer_followup(_fake_analysis().model_dump(), history, "Why down?", mock_llm)
    assert out == "Because PC demand softened."
    prompt = mock_llm.text_calls[0]["prompt"]
    assert "What was revenue?" in prompt and "Why down?" in prompt


# --- endpoints ---

def _client_with_done_contract(tmp_path, monkeypatch):
    init_db(make_engine(f"sqlite:///{tmp_path/'t.db'}"))
    monkeypatch.setattr(contracts_mod, "run_financial_analysis",
                        lambda path, llm, on_progress=None: _fake_analysis())
    monkeypatch.setattr(contracts_mod, "get_llm", lambda: None)
    client = TestClient(create_app())
    cid = client.post("/contracts", files={
        "file": ("intel.pdf", io.BytesIO(b"data"), "application/octet-stream")}).json()["id"]
    client.post(f"/contracts/{cid}/analyze")
    return client, cid


def test_post_followup_persists_turn(tmp_path, monkeypatch):
    client, cid = _client_with_done_contract(tmp_path, monkeypatch)
    monkeypatch.setattr(followup_mod, "get_llm",
                        lambda: type("L", (), {"generate_text": lambda self, p, **k: "An answer."})())

    r = client.post(f"/contracts/{cid}/followup", json={"question": "What drove revenue?"})
    assert r.status_code == 200
    msgs = r.json()["messages"]
    assert [m["role"] for m in msgs] == ["user", "assistant"]
    assert msgs[0]["content"] == "What drove revenue?"
    assert msgs[1]["content"] == "An answer."

    # GET returns the same persisted thread.
    got = client.get(f"/contracts/{cid}/followup").json()["messages"]
    assert len(got) == 2


def test_followup_history_is_threaded(tmp_path, monkeypatch):
    client, cid = _client_with_done_contract(tmp_path, monkeypatch)
    seen = {}

    class L:
        def generate_text(self, prompt, **k):
            seen["prompt"] = prompt
            return "ok"

    monkeypatch.setattr(followup_mod, "get_llm", lambda: L())
    client.post(f"/contracts/{cid}/followup", json={"question": "first question"})
    client.post(f"/contracts/{cid}/followup", json={"question": "second question"})
    # The second call's prompt must contain the first turn.
    assert "first question" in seen["prompt"]
    assert "second question" in seen["prompt"]


def test_post_followup_requires_done(tmp_path):
    init_db(make_engine(f"sqlite:///{tmp_path/'t.db'}"))
    client = TestClient(create_app())
    cid = client.post("/contracts", files={
        "file": ("x.pdf", io.BytesIO(b"data"), "application/octet-stream")}).json()["id"]
    # status is "uploaded", not "done"
    r = client.post(f"/contracts/{cid}/followup", json={"question": "hi"})
    assert r.status_code == 400


def test_post_followup_rejects_empty_question(tmp_path, monkeypatch):
    client, cid = _client_with_done_contract(tmp_path, monkeypatch)
    r = client.post(f"/contracts/{cid}/followup", json={"question": "   "})
    assert r.status_code == 400


def test_followup_unknown_contract_404(tmp_path):
    init_db(make_engine(f"sqlite:///{tmp_path/'t.db'}"))
    client = TestClient(create_app())
    assert client.get("/contracts/999/followup").status_code == 404
    assert client.post("/contracts/999/followup", json={"question": "hi"}).status_code == 404


def test_delete_contract_removes_followups(tmp_path, monkeypatch):
    client, cid = _client_with_done_contract(tmp_path, monkeypatch)
    monkeypatch.setattr(followup_mod, "get_llm",
                        lambda: type("L", (), {"generate_text": lambda self, p, **k: "a"})())
    client.post(f"/contracts/{cid}/followup", json={"question": "q"})
    assert client.delete(f"/contracts/{cid}").status_code == 200
    # contract gone → 404 (proves rows were cleaned without orphaning)
    assert client.get(f"/contracts/{cid}/followup").status_code == 404
