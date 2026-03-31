from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder


BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
DATASET_PATH = PROJECT_ROOT / "data" / "classification_dataset.json"
ARTIFACTS_DIR = BASE_DIR / "artifacts"
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
MODEL_PATH = ARTIFACTS_DIR / "classifier.joblib"
METADATA_PATH = ARTIFACTS_DIR / "metadata.json"


def build_text(sample: dict[str, Any]) -> str:
    statement = str(sample.get("statement", "") or "")
    code = str(sample.get("code", "") or "")
    verdict = str(sample.get("verdict", "") or "")
    return (
        f"Statement:\n{statement}\n\n"
        f"Code:\n{code}\n\n"
        f"Verdict:\n{verdict}"
    )


def load_dataset(path: Path) -> tuple[list[str], list[str]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("classification_dataset.json must contain a list.")

    texts: list[str] = []
    labels: list[str] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        label = str(item.get("error_type", "") or "").strip()
        if not label:
            continue
        texts.append(build_text(item))
        labels.append(label)

    if not texts:
        raise ValueError("Dataset is empty after filtering labels.")
    return texts, labels


def choose_split(labels: list[str], test_size: float, random_state: int) -> tuple[np.ndarray, ...]:
    label_counts = Counter(labels)
    can_stratify = len(label_counts) > 1 and min(label_counts.values()) >= 2
    return train_test_split(
        np.arange(len(labels)),
        test_size=test_size,
        random_state=random_state,
        stratify=labels if can_stratify else None,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=str, default=str(DATASET_PATH))
    parser.add_argument("--model-name", type=str, default="all-MiniLM-L6-v2")
    parser.add_argument("--test-size", type=float, default=0.2)
    parser.add_argument("--random-state", type=int, default=42)
    args = parser.parse_args()

    dataset_path = Path(args.dataset)
    texts, labels = load_dataset(dataset_path)

    le = LabelEncoder()
    y = le.fit_transform(labels)
    train_idx, test_idx = choose_split(labels, test_size=args.test_size, random_state=args.random_state)

    encoder = SentenceTransformer(args.model_name)
    x_train = encoder.encode([texts[i] for i in train_idx], show_progress_bar=True, convert_to_numpy=True)
    x_test = encoder.encode([texts[i] for i in test_idx], show_progress_bar=False, convert_to_numpy=True)

    y_train = y[train_idx]
    y_test = y[test_idx]

    clf = LogisticRegression(max_iter=2000, class_weight="balanced")
    clf.fit(x_train, y_train)

    pred = clf.predict(x_test)
    acc = accuracy_score(y_test, pred)
    all_label_ids = np.arange(len(le.classes_))
    report = classification_report(
        y_test,
        pred,
        labels=all_label_ids,
        target_names=le.classes_,
        zero_division=0,
    )

    print(f"Train size: {len(train_idx)} | Test size: {len(test_idx)}")
    print(f"Accuracy: {acc:.4f}")
    print(report)

    bundle = {
        "classifier": clf,
        "label_encoder": le,
        "embedding_model_name": args.model_name,
    }
    joblib.dump(bundle, MODEL_PATH)

    metadata = {
        "dataset_path": str(dataset_path),
        "n_samples": len(texts),
        "n_train": int(len(train_idx)),
        "n_test": int(len(test_idx)),
        "test_size": args.test_size,
        "random_state": args.random_state,
        "embedding_model_name": args.model_name,
        "labels": list(le.classes_),
        "accuracy": float(acc),
    }
    METADATA_PATH.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(f"Saved model to: {MODEL_PATH}")
    print(f"Saved metadata to: {METADATA_PATH}")


if __name__ == "__main__":
    main()
