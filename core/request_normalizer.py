"""
Convert dataset loader items into the final canonical request schema.
"""
from typing import Any, Dict

from core.schemas import NormalizedSample


class RequestNormalizer:
    """Build the final normalized sample schema for inference and evaluation."""

    def normalize_data_item(self, data_item: Any) -> NormalizedSample:
        if isinstance(data_item, NormalizedSample):
            return data_item

        metadata = {
            "source_file": getattr(data_item, "source_file", ""),
            "source_row": getattr(data_item, "source_row", 0),
            "question_type": getattr(data_item, "question_type", ""),
            "canonical_fields": getattr(data_item, "canonical_fields", {}),
            "raw_metadata": getattr(data_item, "raw_metadata", {}),
        }
        return NormalizedSample(
            sample_id=data_item.sample_id,
            task_key=data_item.task_key,
            task_type=data_item.task_type,
            task_family=data_item.task_family,
            subject=data_item.subject or "",
            education_level=data_item.education_level or "",
            lang=data_item.lang,
            question=data_item.question or data_item.prompt,
            prompt_text=data_item.prompt,
            expected_output_format=data_item.expected_output_format,
            ground_truth=data_item.ground_truth,
            metadata=metadata,
        )

    def build_primary_benchmark_sample(
        self,
        raw_item: Dict[str, Any],
        task_key: str,
        lang: str,
        source_file: str,
        line_index: int,
    ) -> NormalizedSample:
        from data_loader import DataLoader

        loader = DataLoader(enable_debug_sampling=False)
        data_item = loader._parse_item(raw_item, task_key, lang, source_file, line_index)
        if data_item is None:
            raise ValueError(f"Failed to normalize task={task_key} lang={lang} row={line_index}")
        return self.normalize_data_item(data_item)
