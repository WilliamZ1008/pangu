"""
Deterministic rule baseline router.

This file is kept only as the baseline route heuristic for experiments.
"""
import re
from typing import Any, Dict

from config import DIFFICULTY_KEYWORDS, SUBJECT_KEYWORDS


class DifficultyDecision:
    """Rule-based baseline router for fast/slow routing."""

    def __init__(self):
        self.difficulty_keywords = DIFFICULTY_KEYWORDS
        self.subject_keywords = SUBJECT_KEYWORDS

    def decide(self, data_item: Any) -> Dict[str, Any]:
        features = self._extract_features(data_item)
        difficulty_score = self._calculate_difficulty(features)
        task_strategy = self._get_task_strategy(data_item.task_type)
        route = self._make_decision(difficulty_score, task_strategy)
        reason = self._build_reason(route, difficulty_score, task_strategy, features)
        return {
            "route": route,
            "reason": reason,
            "difficulty_score": difficulty_score,
            "task_strategy": task_strategy,
            "features": features,
        }

    def get_decision_explanation(self, data_item: Any) -> Dict[str, Any]:
        return self.decide(data_item)

    def _extract_features(self, data_item: Any) -> Dict[str, Any]:
        question = data_item.question or data_item.prompt
        prompt = data_item.prompt or data_item.question
        subject = (data_item.subject or "").lower()
        education_level = (data_item.education_level or "").lower()
        question_type = (data_item.question_type or "").lower()
        return {
            "task_type": data_item.task_type,
            "subject": subject,
            "education_level": education_level,
            "question_type": question_type,
            "question_length": len(question),
            "prompt_length": len(prompt),
            "has_options": "选项" in question or "options" in question.lower(),
            "has_multi_choice": "多选" in question_type or "multiple" in question_type.lower(),
            "has_math": bool(
                re.search(r"[\d\+\-\*/=\(\)]+", question)
                or any(keyword in subject for keyword in self.subject_keywords["math"])
            ),
        }

    def _calculate_difficulty(self, features: Dict[str, Any]) -> float:
        score = 0.5

        education_level = features["education_level"]
        for keyword in self.difficulty_keywords["easy"]:
            if keyword in education_level:
                score -= 0.3
                break
        for keyword in self.difficulty_keywords["hard"]:
            if keyword in education_level:
                score += 0.3
                break

        if features["question_length"] < 50:
            score -= 0.15
        elif features["question_length"] > 200:
            score += 0.15

        if features["has_options"] and not features["has_multi_choice"]:
            score -= 0.1
        elif features["has_multi_choice"]:
            score += 0.1
        elif any(
            keyword in features["question_type"]
            for keyword in ["解答", "分析", "证明", "solve", "analyze", "prove"]
        ):
            score += 0.2

        if features["has_math"]:
            score += 0.1

        return max(0.0, min(1.0, score))

    def _get_task_strategy(self, task_type: str) -> str:
        if task_type == "question_answering":
            return "adaptive"
        if task_type in {
            "automatic_grading",
            "error_correction",
            "idea_prompting",
            "personalized_content",
            "personalized_learning",
            "question_generation",
            "teaching_material",
            "emotional_support",
        }:
            return "slow"
        return "adaptive"

    def _make_decision(self, difficulty_score: float, task_strategy: str) -> str:
        if task_strategy == "slow":
            return "slow"
        if difficulty_score < 0.35:
            return "fast"
        if difficulty_score < 0.65:
            return "slow_then_fast"
        return "slow"

    def _build_reason(
        self,
        route: str,
        difficulty_score: float,
        task_strategy: str,
        features: Dict[str, Any],
    ) -> str:
        reason_parts = [
            f"baseline rule router",
            f"task_strategy={task_strategy}",
            f"difficulty_score={difficulty_score:.2f}",
            f"question_length={features['question_length']}",
        ]
        if features["has_math"]:
            reason_parts.append("math-like content detected")
        if features["has_multi_choice"]:
            reason_parts.append("multi-choice signal detected")
        reason_parts.append(f"route={route}")
        return "; ".join(reason_parts)


if __name__ == "__main__":
    from data_loader import DataItem

    test_items = [
        DataItem(
            sample_id="demo_qa",
            task_key="Q&A",
            task_type="question_answering",
            task_family="answering",
            expected_output_format="text_answer",
            prompt="1+1等于多少？",
            question="1+1等于多少？",
            ground_truth="2",
            subject="数学",
            education_level="小学",
            question_type="单选题",
        ),
        DataItem(
            sample_id="demo_qg",
            task_key="QG",
            task_type="question_generation",
            task_family="generation",
            expected_output_format="json_question_bundle",
            prompt="知识点: 勾股定理",
            question="勾股定理",
            ground_truth={"question": "示例"},
            subject="数学",
            education_level="高中",
            question_type="解答题",
        ),
    ]

    router = DifficultyDecision()
    for item in test_items:
        print(router.decide(item))
