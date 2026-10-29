"""Independent business contracts; no legacy EIQAS objects or Agent state."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

Stage = Literal["question", "plan", "data", "analysis", "review"]
Text = Annotated[str, Field(min_length=1, max_length=20000, strict=True)]
Identifier = Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$", strict=True)]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ResearchCreate(Contract):
    thread_id: Identifier
    question: Text


class Method(Contract):
    name: Text
    rationale: Text
    operation: Literal["aggregate", "growth", "structure", "contribution", "correlation", "cost_benefit", "sensitivity", "python", "evidence_review"]
    id: Identifier | None = None
    selected: bool = True
    role: Literal["primary", "supporting"] = "primary"
    question_ids: list[Identifier] = Field(default_factory=list, max_length=30)
    basis: str = Field(default="", max_length=20000)
    calculation: str = Field(default="", max_length=20000)
    applicability: str = Field(default="", max_length=20000)
    expected_outputs: list[Text] = Field(default_factory=list, max_length=30)


class ResearchQuestion(Contract):
    id: Identifier
    text: Text


class QuestionDecision(Contract):
    question_id: Identifier
    status: Literal["answer", "partial", "unanswerable"]
    explanation: Text


class DataRequirement(Contract):
    id: Identifier
    title: Text
    method_ids: list[Identifier] = Field(min_length=1, max_length=30)
    kind: Literal["quantitative", "context"]
    required: bool = True
    category: Literal["public", "internal", "expert", "commercial", "collection", "unknown"]
    fields: list[Text] = Field(min_length=1, max_length=100)
    metrics: list[Text] = Field(default_factory=list, max_length=100)
    grain: Text
    period: Text
    units: Text
    channels: list[Text] = Field(min_length=1, max_length=20)
    impact_if_missing: Text
    fallback: Text


class Plan(Contract):
    question: Text
    methods: list[Method] = Field(min_length=1, max_length=30)
    required_data: list[Text] = Field(min_length=1, max_length=100)
    assumptions: list[Text] = Field(default_factory=list, max_length=100)
    outputs: list[Text] = Field(min_length=1, max_length=100)
    limitations: list[Text] = Field(default_factory=list, max_length=100)
    decision_use: str = Field(default="", max_length=20000)
    scope: str = Field(default="", max_length=20000)
    research_questions: list[ResearchQuestion] = Field(default_factory=list, max_length=30)
    question_decisions: list[QuestionDecision] = Field(default_factory=list, max_length=30)
    data_requirements: list[DataRequirement] = Field(default_factory=list, max_length=100)
    data_constraints: list[Text] = Field(default_factory=list, max_length=100)
    scope_changes: list[Text] = Field(default_factory=list, max_length=100)
    open_questions: list[Text] = Field(default_factory=list, max_length=30)


class QuestionUpdate(Contract):
    question: Text


class Confirmation(Contract):
    plan_hash: Text


class StageUpdate(Contract):
    stage: Stage


class ScopeUpdate(Contract):
    answerable: list[Text] = Field(default_factory=list, max_length=100)
    gaps: list[Text] = Field(default_factory=list, max_length=100)


class ObservationCorrection(Contract):
    value: Text
    unit: Text
    reason: Text
    subject: Text | None = None
    period: Text | None = None
    metric: Text | None = None
    qualifier: Literal["exact", "about", "more_than", "less_than", "range"] | None = None
