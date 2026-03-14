"""
Canonical EduBench loader for reproducible offline experiments.
"""
import hashlib
import json
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

from config import (
    DEBUG_SAMPLE_SIZE,
    DEV_RATIO,
    ENABLE_DEBUG_SAMPLING,
    EN_DATA_DIR,
    PRIMARY_TASK_KEYS,
    RANDOM_SEED,
    SUPPLEMENTARY_TASK_KEYS,
    TASK_TYPES,
    ZH_DATA_DIR,
)


TASK_FAMILIES = {
    "Q&A": "answering",
    "AG": "grading",
    "EC": "correction",
    "IP": "guidance",
    "PCC": "planning",
    "PLS": "personalized_content",
    "QG": "generation",
    "TMG": "generation",
    "ES": "support",
}

EXPECTED_OUTPUT_FORMATS = {
    "Q&A": "text_answer",
    "AG": "json_score_feedback",
    "EC": "json_correction",
    "IP": "json_guidance",
    "PCC": "json_learning_plan",
    "PLS": "json_personalized_learning_content",
    "QG": "json_question_bundle",
    "TMG": "json_teaching_materials",
    "ES": "json_emotional_support",
}

LANG_DIRS = {
    "zh": Path(ZH_DATA_DIR),
    "en": Path(EN_DATA_DIR),
}

SPLIT_ALIASES = {
    "all": "all",
    "dev": "dev",
    "test": "test",
    "ablation": "dev",
}


def _first_present(raw: Dict[str, Any], *keys: str, default: Any = "") -> Any:
    for key in keys:
        if key in raw and raw[key] not in (None, ""):
            return raw[key]
    return default


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)
    return str(value).strip()


def _is_empty(value: Any) -> bool:
    return value in (None, "", [], {})


def _render_value(value: Any, indent: int = 0) -> List[str]:
    prefix = " " * indent
    if isinstance(value, dict):
        lines: List[str] = []
        for key, nested_value in value.items():
            if _is_empty(nested_value):
                continue
            if isinstance(nested_value, (dict, list)):
                lines.append(f"{prefix}{key}:")
                lines.extend(_render_value(nested_value, indent + 2))
            else:
                lines.append(f"{prefix}{key}: {_as_text(nested_value)}")
        return lines
    if isinstance(value, list):
        lines = []
        for item in value:
            if isinstance(item, (dict, list)):
                lines.append(f"{prefix}-")
                lines.extend(_render_value(item, indent + 2))
            else:
                lines.append(f"{prefix}- {_as_text(item)}")
        return lines
    return [f"{prefix}{_as_text(value)}"]


def _build_sectioned_prompt(sections: Sequence[tuple[str, Any]]) -> str:
    lines: List[str] = []
    for title, value in sections:
        if _is_empty(value):
            continue
        lines.append(f"{title}:")
        lines.extend(_render_value(value, 2))
        lines.append("")
    return "\n".join(lines).strip()


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _stable_seed(*parts: str) -> int:
    digest = hashlib.sha1("::".join(parts).encode("utf-8")).hexdigest()
    return int(digest[:16], 16)


def _dev_size(total: int) -> int:
    if total <= 1:
        return total
    return max(1, int(total * DEV_RATIO + 0.5))


@dataclass
class DataItem:
    sample_id: str
    task_key: str
    task_type: str
    task_family: str
    expected_output_format: str
    prompt: str
    question: str
    ground_truth: Any
    subject: str = ""
    education_level: str = ""
    question_type: str = ""
    lang: str = "zh"
    source_file: str = ""
    source_row: int = 0
    canonical_fields: Dict[str, Any] = field(default_factory=dict)
    raw_metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def answer(self) -> Any:
        return self.ground_truth

    @property
    def raw_data(self) -> Dict[str, Any]:
        return self.raw_metadata

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sample_id": self.sample_id,
            "task_key": self.task_key,
            "task_type": self.task_type,
            "task_family": self.task_family,
            "expected_output_format": self.expected_output_format,
            "prompt": self.prompt,
            "question": self.question,
            "ground_truth": self.ground_truth,
            "subject": self.subject,
            "education_level": self.education_level,
            "question_type": self.question_type,
            "lang": self.lang,
            "source_file": self.source_file,
            "source_row": self.source_row,
            "canonical_fields": self.canonical_fields,
        }


class DataLoader:
    """Deterministic EduBench loader with canonical prompts and splits."""

    def __init__(
        self,
        zh_data_dir: str = ZH_DATA_DIR,
        en_data_dir: str = EN_DATA_DIR,
        enable_debug_sampling: bool = ENABLE_DEBUG_SAMPLING,
        debug_sample_size: Optional[int] = None,
    ):
        self.lang_dirs = {
            "zh": Path(zh_data_dir),
            "en": Path(en_data_dir),
        }
        self.enable_debug_sampling = enable_debug_sampling
        self.debug_sample_size = debug_sample_size or DEBUG_SAMPLE_SIZE

    def load_primary_all(self) -> List[DataItem]:
        items: List[DataItem] = []
        for lang in ("zh", "en"):
            items.extend(self.load_primary_split(lang, "all"))
        return items

    def load_primary_split(self, lang: str, split: str) -> List[DataItem]:
        split_name = self._normalize_split(split)
        langs = ("zh", "en") if lang == "all" else (lang,)
        items: List[DataItem] = []
        for lang_name in langs:
            for task_key in PRIMARY_TASK_KEYS:
                items.extend(self.load_task_split(task_key, lang_name, split_name))
        return items

    def load_task_split(self, task_key: str, lang: str, split: str) -> List[DataItem]:
        normalized_task_key = self._normalize_task_key(task_key)
        if normalized_task_key not in PRIMARY_TASK_KEYS + SUPPLEMENTARY_TASK_KEYS:
            raise ValueError(f"Unsupported task key: {task_key}")
        if lang not in self.lang_dirs:
            raise ValueError(f"Unsupported language: {lang}")

        split_name = self._normalize_split(split)
        file_path = self.lang_dirs[lang] / f"{normalized_task_key}.jsonl"
        if not file_path.exists():
            return []

        items = self._load_task_file(file_path, lang, normalized_task_key)
        split_items = self._apply_split(items, lang, normalized_task_key, split_name)
        return self._apply_debug_sampling(split_items)

    def load_all(self) -> List[DataItem]:
        """Backward-compatible alias for the shared-8 benchmark."""
        return self.load_primary_all()

    def load_by_task(self, task_key: str, lang: str = "all", split: str = "all") -> List[DataItem]:
        normalized_task_key = self._normalize_task_key(task_key)
        if lang == "all":
            items: List[DataItem] = []
            for lang_name in ("zh", "en"):
                items.extend(self.load_task_split(normalized_task_key, lang_name, split))
            return items
        return self.load_task_split(normalized_task_key, lang, split)

    def build_count_report(self) -> Dict[str, Any]:
        report: Dict[str, Any] = {"primary": {}}
        for lang in ("zh", "en"):
            task_counts = {}
            total = 0
            for task_key in PRIMARY_TASK_KEYS:
                count = len(self.load_task_split(task_key, lang, "all"))
                task_counts[task_key] = count
                total += count
            report["primary"][lang] = {"tasks": task_counts, "total": total}
        return report

    def build_split_report(self) -> Dict[str, Any]:
        report: Dict[str, Any] = {}
        for lang in ("zh", "en"):
            per_task = {}
            dev_total = 0
            test_total = 0
            for task_key in PRIMARY_TASK_KEYS:
                dev_count = len(self.load_task_split(task_key, lang, "dev"))
                test_count = len(self.load_task_split(task_key, lang, "test"))
                per_task[task_key] = {"dev": dev_count, "test": test_count}
                dev_total += dev_count
                test_total += test_count
            report[lang] = {"tasks": per_task, "dev_total": dev_total, "test_total": test_total}
        return report

    def _normalize_task_key(self, task_key: str) -> str:
        if task_key in TASK_TYPES:
            return task_key
        reverse_map = {value: key for key, value in TASK_TYPES.items()}
        if task_key in reverse_map:
            return reverse_map[task_key]
        raise ValueError(f"Unknown task key or task type: {task_key}")

    def _normalize_split(self, split: str) -> str:
        split_key = split.strip().lower()
        if split_key not in SPLIT_ALIASES:
            raise ValueError(f"Unsupported split: {split}")
        return SPLIT_ALIASES[split_key]

    def _apply_debug_sampling(self, items: List[DataItem]) -> List[DataItem]:
        if not self.enable_debug_sampling:
            return items
        return items[: self.debug_sample_size]

    def _apply_split(self, items: List[DataItem], lang: str, task_key: str, split: str) -> List[DataItem]:
        if split == "all":
            return list(items)

        shuffled = sorted(items, key=lambda item: item.sample_id)
        rnd = random.Random(_stable_seed(str(RANDOM_SEED), lang, task_key))
        rnd.shuffle(shuffled)

        dev_boundary = _dev_size(len(shuffled))
        if split == "dev":
            subset = shuffled[:dev_boundary]
        else:
            subset = shuffled[dev_boundary:]

        return sorted(subset, key=lambda item: item.source_row)

    def _load_task_file(self, file_path: Path, lang: str, task_key: str) -> List[DataItem]:
        items: List[DataItem] = []
        with file_path.open("r", encoding="utf-8") as handle:
            for row_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                raw = json.loads(line)
                item = self._parse_item(raw, task_key, lang, file_path.name, row_number)
                if item is not None:
                    items.append(item)
        return items

    def _parse_item(
        self,
        raw: Dict[str, Any],
        task_key: str,
        lang: str,
        source_file: str,
        source_row: int,
    ) -> Optional[DataItem]:
        subject = _as_text(_first_present(raw, "学科", "Subject"))
        education_level = _as_text(
            _first_present(raw, "学制级别", "Education Level", "Level", "难度", "Difficulty")
        )
        question_type = _as_text(_first_present(raw, "题型", "Question Type"))

        parser_name = f"_parse_{task_key.lower().replace('&', 'and')}"
        parser = getattr(self, parser_name, None)
        if parser is None:
            return None

        parsed = parser(raw, lang, subject, education_level, question_type)
        if parsed is None:
            return None

        prompt = parsed["prompt"].strip()
        question = parsed.get("question", prompt).strip() or prompt
        ground_truth = parsed["ground_truth"]
        canonical_fields = parsed["canonical_fields"]

        sample_id = self._build_sample_id(
            task_key=task_key,
            lang=lang,
            source_file=source_file,
            source_row=source_row,
            prompt=prompt,
            ground_truth=ground_truth,
        )

        return DataItem(
            sample_id=sample_id,
            task_key=task_key,
            task_type=TASK_TYPES[task_key],
            task_family=TASK_FAMILIES[task_key],
            expected_output_format=EXPECTED_OUTPUT_FORMATS[task_key],
            prompt=prompt,
            question=question,
            ground_truth=ground_truth,
            subject=subject,
            education_level=education_level,
            question_type=question_type,
            lang=lang,
            source_file=source_file,
            source_row=source_row,
            canonical_fields=canonical_fields,
            raw_metadata=raw,
        )

    def _build_sample_id(
        self,
        task_key: str,
        lang: str,
        source_file: str,
        source_row: int,
        prompt: str,
        ground_truth: Any,
    ) -> str:
        digest_input = {
            "task_key": task_key,
            "lang": lang,
            "source_file": source_file,
            "source_row": source_row,
            "prompt": prompt,
            "ground_truth": ground_truth,
        }
        digest = hashlib.sha1(_canonical_json(digest_input).encode("utf-8")).hexdigest()[:12]
        return f"{lang}_{task_key}_{source_row:05d}_{digest}"

    def _parse_qanda(
        self,
        raw: Dict[str, Any],
        lang: str,
        subject: str,
        education_level: str,
        question_type: str,
    ) -> Dict[str, Any]:
        question = _as_text(_first_present(raw, "问题", "Question"))
        answer = _first_present(raw, "答案", "Answer")
        return {
            "prompt": question,
            "question": question,
            "ground_truth": answer,
            "canonical_fields": {
                "question": question,
                "subject": subject,
                "education_level": education_level,
                "question_type": question_type,
            },
        }

    def _parse_ag(
        self,
        raw: Dict[str, Any],
        lang: str,
        subject: str,
        education_level: str,
        question_type: str,
    ) -> Dict[str, Any]:
        question_field = _first_present(raw, "问题", "Question")
        if isinstance(question_field, dict):
            question_body = _build_sectioned_prompt(
                [("题目" if lang == "zh" else "Question", question_field.get("题目") or question_field.get("Question"))]
            )
            options = question_field.get("选项") or question_field.get("Options")
            if options:
                question_body = _build_sectioned_prompt(
                    [
                        ("题目" if lang == "zh" else "Question", question_field.get("题目") or question_field.get("Question")),
                        ("选项" if lang == "zh" else "Options", options),
                    ]
                )
        else:
            question_body = _as_text(question_field)

        student_answer = _first_present(raw, "学生的答案", "Student's Answer")
        prompt = _build_sectioned_prompt(
            [
                ("问题" if lang == "zh" else "Question", question_body),
                ("学生答案" if lang == "zh" else "Student Answer", student_answer),
            ]
        )
        ground_truth = {
            "score": _first_present(raw, "评分", "Score"),
            "score_detail": _first_present(raw, "评分细节", "Scoring Details"),
            "personalized_feedback": _first_present(raw, "个性化反馈", "Personalized Feedback"),
        }
        return {
            "prompt": prompt,
            "question": question_body,
            "ground_truth": ground_truth,
            "canonical_fields": {
                "question": question_body,
                "student_answer": student_answer,
            },
        }

    def _parse_ec(
        self,
        raw: Dict[str, Any],
        lang: str,
        subject: str,
        education_level: str,
        question_type: str,
    ) -> Dict[str, Any]:
        question = _as_text(_first_present(raw, "问题", "Question"))
        original_answer = _first_present(raw, "原答案", "Original Answer")
        prompt = _build_sectioned_prompt(
            [
                ("问题" if lang == "zh" else "Question", question),
                ("原答案" if lang == "zh" else "Original Answer", original_answer),
            ]
        )
        ground_truth = {
            "corrected_answer": _first_present(raw, "纠错后答案", "Corrected Answer"),
            "correction_explanation": _first_present(raw, "纠错说明", "Correction Explanation"),
        }
        return {
            "prompt": prompt,
            "question": question,
            "ground_truth": ground_truth,
            "canonical_fields": {
                "question": question,
                "original_answer": original_answer,
            },
        }

    def _parse_ip(
        self,
        raw: Dict[str, Any],
        lang: str,
        subject: str,
        education_level: str,
        question_type: str,
    ) -> Dict[str, Any]:
        question = _as_text(_first_present(raw, "问题", "Question"))
        prompt = question
        ground_truth = {
            "guidance": _first_present(raw, "提供的思路", "Guidance Provided", "Reasoning Provided")
        }
        return {
            "prompt": prompt,
            "question": question,
            "ground_truth": ground_truth,
            "canonical_fields": {
                "question": question,
            },
        }

    def _parse_pcc(
        self,
        raw: Dict[str, Any],
        lang: str,
        subject: str,
        education_level: str,
        question_type: str,
    ) -> Dict[str, Any]:
        student_profile = _first_present(raw, "学生画像", "学生的画像", "Student Profile")
        prompt = _build_sectioned_prompt(
            [
                ("学生画像" if lang == "zh" else "Student Profile", student_profile),
            ]
        )
        ground_truth = {
            "learning_path_planning": _first_present(raw, "学习路径规划建议", "Learning Path Planning"),
            "personalized_recommendations": _first_present(raw, "个性化意见生成", "Personalized Recommendations"),
        }
        return {
            "prompt": prompt,
            "question": _as_text(student_profile),
            "ground_truth": ground_truth,
            "canonical_fields": {
                "student_profile": student_profile,
            },
        }

    def _parse_pls(
        self,
        raw: Dict[str, Any],
        lang: str,
        subject: str,
        education_level: str,
        question_type: str,
    ) -> Dict[str, Any]:
        student_profile = _first_present(raw, "学生的画像", "学生画像", "Student Profile")
        prompt = _build_sectioned_prompt(
            [
                ("学生画像" if lang == "zh" else "Student Profile", student_profile),
            ]
        )
        ground_truth = {
            "personalized_learning_content": _first_present(
                raw, "个性化学习内容/任务", "Personalized Learning Content/Task"
            )
        }
        return {
            "prompt": prompt,
            "question": _as_text(student_profile),
            "ground_truth": ground_truth,
            "canonical_fields": {
                "student_profile": student_profile,
            },
        }

    def _parse_qg(
        self,
        raw: Dict[str, Any],
        lang: str,
        subject: str,
        education_level: str,
        question_type: str,
    ) -> Dict[str, Any]:
        knowledge_point = _first_present(raw, "知识点", "Knowledge Point")
        prompt = _build_sectioned_prompt(
            [
                ("学科" if lang == "zh" else "Subject", subject),
                ("学制级别" if lang == "zh" else "Education Level", education_level),
                ("题型" if lang == "zh" else "Question Type", question_type),
                ("知识点" if lang == "zh" else "Knowledge Point", knowledge_point),
            ]
        )
        ground_truth = {
            "question": _first_present(raw, "问题", "Question"),
            "guidance": _first_present(raw, "提供的思路", "提供的思路", "Solution Guidance", "Provided Reasoning"),
            "answer": _first_present(raw, "答案", "Answer"),
        }
        return {
            "prompt": prompt,
            "question": _as_text(knowledge_point),
            "ground_truth": ground_truth,
            "canonical_fields": {
                "subject": subject,
                "education_level": education_level,
                "question_type": question_type,
                "knowledge_point": knowledge_point,
            },
        }

    def _parse_tmg(
        self,
        raw: Dict[str, Any],
        lang: str,
        subject: str,
        education_level: str,
        question_type: str,
    ) -> Dict[str, Any]:
        knowledge_point = _first_present(raw, "知识点", "Knowledge Point")
        prompt = _build_sectioned_prompt(
            [
                ("学科" if lang == "zh" else "Subject", subject),
                ("学制级别" if lang == "zh" else "Education Level", education_level),
                ("题型" if lang == "zh" else "Question Type", question_type),
                ("知识点" if lang == "zh" else "Knowledge Point", knowledge_point),
            ]
        )
        ground_truth = {
            "teaching_materials": _first_present(raw, "教学素材", "Teaching Materials")
        }
        return {
            "prompt": prompt,
            "question": _as_text(knowledge_point),
            "ground_truth": ground_truth,
            "canonical_fields": {
                "subject": subject,
                "education_level": education_level,
                "question_type": question_type,
                "knowledge_point": knowledge_point,
            },
        }

    def _parse_es(
        self,
        raw: Dict[str, Any],
        lang: str,
        subject: str,
        education_level: str,
        question_type: str,
    ) -> Dict[str, Any]:
        anxiety_level = _first_present(raw, "焦虑等级", "Anxiety Level")
        dialogue = _first_present(raw, "与学生的对话", "Dialogue with Student")
        prompt = _build_sectioned_prompt(
            [
                ("焦虑等级" if lang == "zh" else "Anxiety Level", anxiety_level),
                ("与学生的对话" if lang == "zh" else "Dialogue with Student", dialogue),
            ]
        )
        ground_truth = {
            "emotional_state_analysis": _first_present(raw, "情绪状态分析", "Emotional State Analysis"),
            "comfort_and_advice": _first_present(raw, "安慰与建议", "Comfort and Advice", "Comfort & Advice"),
        }
        return {
            "prompt": prompt,
            "question": _as_text(dialogue),
            "ground_truth": ground_truth,
            "canonical_fields": {
                "anxiety_level": anxiety_level,
                "dialogue": dialogue,
            },
        }


if __name__ == "__main__":
    loader = DataLoader()
    count_report = loader.build_count_report()
    split_report = loader.build_split_report()

    print(json.dumps(count_report, ensure_ascii=False, indent=2))
    print(json.dumps(split_report, ensure_ascii=False, indent=2))
