"""Investigation Graph runner orchestrating end-to-end AI investigation pipeline."""
from typing import Optional
from sqlalchemy.orm import Session

from backend.agent.graph.state import InvestigationState
from backend.agent.graph.nodes import (
    load_exception_node,
    gather_evidence_node,
    trace_lifecycle_node,
    cross_source_compare_node,
    form_hypotheses_node,
    test_hypotheses_node,
    determine_root_cause_node,
    validate_exposure_node,
    generate_explanation_node,
    persist_investigation_node,
)
from backend.agent.tools.registry import AgentToolRegistry
from backend.agent.provider import LLMProvider, get_llm_provider


class InvestigationGraph:
    """Orchestrates modular investigation pipeline with error handling, retries, and bounded tool execution."""

    def __init__(
        self,
        llm_provider: Optional[LLMProvider] = None,
        max_tool_calls: int = 25,
        max_retries: int = 2,
    ):
        self.llm_provider = llm_provider or get_llm_provider()
        self.tool_registry = AgentToolRegistry(max_tool_calls=max_tool_calls)
        self.max_retries = max_retries

    def run(
        self,
        session: Session,
        exception_id: str,
        reinvestigate: bool = False,
    ) -> InvestigationState:
        """Executes full investigation graph for the given exception with bounded retries."""
        state = InvestigationState(exception_id=exception_id)
        self.tool_registry.reset_call_counter()

        try:
            # 1. Stage: LOAD_EXCEPTION (transitions DETECTED -> INVESTIGATING)
            state = load_exception_node(state, session=session, reinvestigate=reinvestigate)
            if state.status == "FAILED":
                return persist_investigation_node(state, session=session)

            # 2. Stage: GATHER_EVIDENCE (read-only tools across sources)
            state = gather_evidence_node(state, session=session, tool_registry=self.tool_registry)
            if state.status == "FAILED":
                return persist_investigation_node(state, session=session)

            # 3. Stage: TRACE_LIFECYCLE (chronological timeline assembly)
            state = trace_lifecycle_node(state)

            # 4. Stage: CROSS_SOURCE_COMPARE (contradiction & discrepancy detection)
            state = cross_source_compare_node(state)

            # 5. Stage: FORM_HYPOTHESES (generate explanatory hypotheses)
            state = form_hypotheses_node(state)

            # 6. Stage: TEST_HYPOTHESES (evaluate hypotheses against facts)
            state = test_hypotheses_node(state)

            # 7. Stage: DETERMINE_ROOT_CAUSE (with bounded retry for transient provider errors)
            attempts = 0
            while attempts <= self.max_retries:
                state.status = "RUNNING"
                state.error_message = None
                state = determine_root_cause_node(state, llm_provider=self.llm_provider)
                if state.status != "FAILED":
                    break
                attempts += 1

            if state.status == "FAILED":
                return persist_investigation_node(state, session=session)

            # 8. Stage: VALIDATE_EXPOSURE (enforce deterministic arithmetic authority)
            state = validate_exposure_node(state)

            # 9. Stage: GENERATE_EXPLANATION (enforce Facts/Hypothesis/Conclusion separation)
            state = generate_explanation_node(state)

            # 10. Stage: PERSIST_INVESTIGATION (save InvestigationRun, transition to DIAGNOSED, audit event)
            state = persist_investigation_node(state, session=session)

        except Exception as err:
            state.status = "FAILED"
            state.error_message = f"Unhandled pipeline exception: {str(err)}"
            state = persist_investigation_node(state, session=session)

        return state
