"""
FastAPI server that exposes the LLM processing and RAG endpoints.

Selenium/browser automation is handled on the frontend desktop app.

Endpoints:
- GET  /health
- POST /process                     -> run LLM pipeline on provided Markdown text
- POST /training/save_correction    -> persist correction to RAG store

Run: uvicorn backend.server:app --reload
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .doc_agent import convert_document
from .process_fax import process_fax
from .correction_store_rag import RAGCorrectionStore


app = FastAPI()


class ProcessBody(BaseModel):
    input_text: str


class ProcessResult(BaseModel):
    md: str = ""
    date_of_birth: str = ""
    patient_name: str = ""
    provider_name: str = ""
    doc_type: str = ""
    doc_subtype: str = ""
    comment: str = ""


class SaveCorrectionBody(BaseModel):
    doc_text: str
    doc_type: str = ""
    doc_subtype: str = ""


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/process", response_model=ProcessResult)
def process(body: ProcessBody):
    try:
        st = process_fax(body.input_text)

        return ProcessResult(**{
            "md": body.input_text,
            "date_of_birth": st.get("date_of_birth", ""),
            "patient_name": st.get("patient_name", ""),
            "provider_name": st.get("provider_name", ""),
            "doc_type": st.get("doc_type", ""),
            "doc_subtype": st.get("doc_subtype", ""),
            "comment": st.get("comment", ""),
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class ProcessUrlBody(BaseModel):
    url: str


@app.post("/process_url", response_model=ProcessResult)
def process_url(body: ProcessUrlBody):
    try:
        md = convert_document(body.url)
        st = process_fax(md)
        return ProcessResult(**{
            "md": md,
            "date_of_birth": st.get("date_of_birth", ""),
            "patient_name": st.get("patient_name", ""),
            "provider_name": st.get("provider_name", ""),
            "doc_type": st.get("doc_type", ""),
            "doc_subtype": st.get("doc_subtype", ""),
            "comment": st.get("comment", ""),
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/training/save_correction")
def training_save_correction(body: SaveCorrectionBody):
    try:
        store = RAGCorrectionStore()
        corr = {"doc_type": body.doc_type, "doc_subtype": body.doc_subtype}
        store.add(body.doc_text, corr)
        return {"saved": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.server:app", host="0.0.0.0", port=8000, reload=True)
