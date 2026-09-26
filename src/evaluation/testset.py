from __future__ import annotations

from typing import Any

import pandas as pd

from core.utils import first_sentence, normalize_whitespace, write_json


def build_test_set(df: pd.DataFrame, output_path) -> list[dict[str, Any]]:
    """Create a deterministic ten-question benchmark from clean paper data."""
    required_columns = {
        "paper_id",
        "title",
        "summary",
        "authors_joined",
        "categories_joined",
        "published",
    }
    missing_columns = sorted(required_columns.difference(df.columns))
    if missing_columns:
        raise ValueError(f"Clean dataframe is missing columns: {', '.join(missing_columns)}")
    if len(df) < 10:
        raise ValueError("At least 10 clean documents are required to build the test set.")

    candidates = (
        df.sort_values(by=["published", "paper_id"], ascending=[False, True], kind="stable")
        .drop_duplicates(subset=["paper_id"], keep="first")
        .head(10)
        .reset_index(drop=True)
    )
    if len(candidates) < 10:
        raise ValueError("At least 10 unique paper IDs are required to build the test set.")

    # A balanced integer allocation across four task types: 3 + 3 + 2 + 2.
    question_types = [
        "summary",
        "authors",
        "date",
        "categories",
        "summary",
        "authors",
        "date",
        "categories",
        "summary",
        "authors",
    ]
    test_set: list[dict[str, Any]] = []
    for index, (question_type, row) in enumerate(
        zip(question_types, candidates.to_dict(orient="records"), strict=True),
        start=1,
    ):
        title = normalize_whitespace(str(row["title"]))
        question, ground_truth = _build_question_and_answer(question_type, title, row)
        test_set.append(
            {
                "id": f"eval_{index:03d}",
                "question_type": question_type,
                "question": question,
                "ground_truth": ground_truth,
                "ground_truth_doc_ids": [normalize_whitespace(str(row["paper_id"]))],
            }
        )

    write_json(output_path, test_set)
    return test_set


def _build_question_and_answer(
    question_type: str, title: str, row: dict[str, Any]
) -> tuple[str, str]:
    if question_type == "summary":
        return (
            f"What is the summary of the paper '{title}'?",
            first_sentence(str(row["summary"])),
        )
    if question_type == "authors":
        return (
            f"Who authored the paper '{title}'?",
            normalize_whitespace(str(row["authors_joined"])),
        )
    if question_type == "date":
        return (
            f"When was the paper '{title}' published?",
            normalize_whitespace(str(row["published"])),
        )
    if question_type == "categories":
        return (
            f"What categories are associated with the paper '{title}'?",
            normalize_whitespace(str(row["categories_joined"])),
        )
    raise ValueError(f"Unsupported question type: {question_type}")
