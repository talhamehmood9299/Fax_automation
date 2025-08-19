from typing_extensions import TypedDict
from typing import Dict, Any
from langgraph.graph import StateGraph, START, END

class AgentState(TypedDict):
    input_text: str
    date_of_birth: str
    patient_name: str
    provider_name: str
    doc_type: str
    doc_subtype: str
    comment: str

def call_llm_1(state: AgentState) -> dict:
    from .ollama_agent import extract_information
    md = state["input_text"]
    date_of_birth, patient_name, provider_name = extract_information(md)
    return {
        "date_of_birth": date_of_birth,
        "patient_name": patient_name,
        "provider_name": provider_name
    }

def call_llm_2(state: AgentState) -> dict:
    from .ollama_agent import find_doctype
    md = state["input_text"]
    doc_type = find_doctype(md)
    return {"doc_type": doc_type}

def call_llm_3(state: AgentState) -> dict:
    from .ollama_agent import find_sub_doctype
    md = state["input_text"]
    doc_subtype = find_sub_doctype(md)
    return {"doc_subtype": doc_subtype}

def call_llm_4(state: AgentState) ->dict:
    from .ollama_agent import generate_document_comments
    md = state["input_text"]
    comment = generate_document_comments(md)
    return {"comment": comment}

def aggregator(state: dict) -> dict:
    # Define mapping from doc_type to provider_name
    mapping = {
        "Prior Authorization": "Medical a-Records",
        "Medical a-Records": "Prior a-Authorizations",
        "Forms": "Forms A-staff"
    }
    doc_type = state.get("doc_type")
    if doc_type in mapping:
        state["provider_name"] = mapping[doc_type]

    provider_name = state.get("provider_name")
    tokens = ("azz", "fazal")
    if provider_name and any(t in provider_name.casefold() for t in tokens):
        state["provider_name"] = "Asim Ali"
    return state


parallel_builder = StateGraph(AgentState)
parallel_builder.add_node("call_llm_1", call_llm_1)
parallel_builder.add_node("call_llm_2", call_llm_2)
parallel_builder.add_node("call_llm_3", call_llm_3)
parallel_builder.add_node("call_llm_4", call_llm_4)
parallel_builder.add_node("aggregator", aggregator)

parallel_builder.add_edge(START, "call_llm_1")
parallel_builder.add_edge(START, "call_llm_2")
parallel_builder.add_edge(START, "call_llm_3")
parallel_builder.add_edge(START, "call_llm_4")
parallel_builder.add_edge("call_llm_1", "aggregator")
parallel_builder.add_edge("call_llm_2", "aggregator")
parallel_builder.add_edge("call_llm_3", "aggregator")
parallel_builder.add_edge("call_llm_4", "aggregator")
parallel_builder.add_edge("aggregator", END)
parallel_workflow = parallel_builder.compile()

def _apply_rag_corrections(state: dict) -> dict:
    """Query RAG for known corrections and apply them if found.
    Only overrides keys that exist in the stored correction (e.g., doc_type/doc_subtype).
    """
    try:
        from .correction_store_rag import RAGCorrectionStore
        store = RAGCorrectionStore()
        doc_text = state.get("input_text", "")
        if not doc_text:
            return state
        correction: Dict[str, Any] = store.query(doc_text)
        if correction:
            for k in ("doc_type", "doc_subtype"):
                if k in correction and correction[k]:
                    state[k] = correction[k]
    except Exception as e:
        # Fail-safe: if RAG not available, continue without corrections
        print(f"RAG correction lookup failed or unavailable: {e}")
    return state

def init_agent_state() -> AgentState:
    return {
        "input_text": "",
        "date_of_birth": "",
        "patient_name": "",
        "provider_name": "",
        "doc_type": "",
        "doc_subtype": "",
        "comment": ""
    }

def process_fax(input_text: str) -> AgentState:
    state = init_agent_state()
    state["input_text"] = input_text
    state = parallel_workflow.invoke(state)
    # Apply any known user-provided corrections from RAG
    state = _apply_rag_corrections(state)
    return state
