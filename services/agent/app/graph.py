from typing import Any, Awaitable, Callable, TypedDict

from langgraph.graph import END, START, StateGraph

from app.query_catalog import QueryPlan, plan_question, validate_plan


class AgentState(TypedDict, total=False):
    question: str
    plan: QueryPlan | None
    status: str
    rows: list[dict[str, Any]]
    answer: str
    answer_provider: str


def deterministic_answer(plan: QueryPlan, rows: list[dict[str, Any]]) -> str:
    if plan.intent in {"total_violations", "camera_total"}:
        total = rows[0]["total"] if rows else 0
        return f"The database contains {total} matching violation events."
    if plan.intent == "top_violation_type":
        if not rows:
            return "No violation events are stored."
        return f"The most common violation is {rows[0]['violation_type']} with {rows[0]['count']} events."
    if plan.intent == "recent_violations":
        return f"The query returned {len(rows)} recent violation events."
    if plan.intent == "violations_by_type":
        return "Violations by type: " + ", ".join(f"{row['violation_type']}={row['count']}" for row in rows)
    if plan.intent == "violations_by_camera":
        return "Violations by camera: " + ", ".join(f"{row['camera_id']}={row['count']}" for row in rows)
    return "The approved query completed."


class GroundedAgent:
    def __init__(
        self,
        execute_query: Callable[[str, list[Any]], Awaitable[list[dict[str, Any]]]],
        answer_with_model: Callable[[str, str, list[dict[str, Any]]], Awaitable[str]] | None = None,
    ):
        self.execute_query = execute_query
        self.answer_with_model = answer_with_model
        builder = StateGraph(AgentState)
        builder.add_node("plan", self.plan)
        builder.add_node("validate", self.validate)
        builder.add_node("execute", self.execute)
        builder.add_node("answer", self.answer)
        builder.add_edge(START, "plan")
        builder.add_conditional_edges("plan", self.after_plan, {"validate": "validate", "answer": "answer"})
        builder.add_edge("validate", "execute")
        builder.add_edge("execute", "answer")
        builder.add_edge("answer", END)
        self.graph = builder.compile()

    async def plan(self, state: AgentState) -> AgentState:
        plan = plan_question(state["question"])
        if plan is None:
            return {"plan": None, "status": "rejected"}
        return {"plan": plan, "status": "planned"}

    def after_plan(self, state: AgentState) -> str:
        return "validate" if state.get("plan") is not None else "answer"

    async def validate(self, state: AgentState) -> AgentState:
        plan = state["plan"]
        if plan is None:
            return {"status": "rejected"}
        validate_plan(plan)
        return {"status": "validated"}

    async def execute(self, state: AgentState) -> AgentState:
        plan = state["plan"]
        if plan is None:
            return {"status": "rejected", "rows": []}
        rows = await self.execute_query(plan.sql, plan.parameters)
        return {"status": "executed", "rows": rows}

    async def answer(self, state: AgentState) -> AgentState:
        plan = state.get("plan")
        if plan is None:
            return {
                "status": "rejected",
                "rows": [],
                "answer": "I can answer read-only questions about violation totals, cameras, types, and recent events. Write requests and unsupported questions are rejected.",
                "answer_provider": "policy",
            }
        rows = state.get("rows", [])
        if self.answer_with_model is not None:
            try:
                answer = await self.answer_with_model(state["question"], plan.sql, rows)
                return {"status": "answered", "answer": answer, "answer_provider": "ollama"}
            except RuntimeError:
                pass
        return {
            "status": "answered",
            "answer": deterministic_answer(plan, rows),
            "answer_provider": "deterministic",
        }

    async def ask(self, question: str) -> AgentState:
        return await self.graph.ainvoke({"question": question})
