"""
Prompt-based specialist router for the final 7B refinement stage.
"""
from core.schemas import NormalizedSample, RouterOutput


class ExpertRouter:
    """Select one prompt-specialized 7B role based on task family."""

    TASK_KEY_TO_SPECIALIST = {
        "Q&A": "reasoning",
        "EC": "reasoning",
        "IP": "reasoning",
        "AG": "assessment",
        "PCC": "planning",
        "PLS": "planning",
        "QG": "planning",
        "TMG": "planning",
    }

    def select(self, sample: NormalizedSample, router_output: RouterOutput | None = None) -> str:
        specialist = self.TASK_KEY_TO_SPECIALIST.get(sample.task_key)
        if specialist:
            return specialist

        predicted_family = (router_output.predicted_task_family if router_output else "") or sample.task_family
        if predicted_family == "grading":
            return "assessment"
        if predicted_family in {"planning", "personalized_content", "generation"}:
            return "planning"
        return "reasoning"
