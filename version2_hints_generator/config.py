from __future__ import annotations

from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

MERGED_PROBLEMS_PATH = (
    PROJECT_ROOT / "results_merged_for_hints_generator" / "code_solution_hints_tutorial_saved.json"
)
SUBMISSIONS_PATH = (
    PROJECT_ROOT / "results_merged_for_hints_generator" / "submission_verdict.json"
)

FEEDBACK_LOG_PATH = DATA_DIR / "feedback_log.jsonl"
PREFERENCE_PAIRS_PATH = DATA_DIR / "reward_pairs.jsonl"
CLASSIFICATION_DATASET_PATH = DATA_DIR / "classification_dataset.json"

DEFAULT_MODEL = "gpt-4o-mini"
# DEFAULT_OLLAMA_MODEL = "qwen2.5-coder"
DEFAULT_OLLAMA_MODEL = "gpt-oss:20b"
DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"
N_HINTS = 3
