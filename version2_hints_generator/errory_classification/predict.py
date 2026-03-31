from __future__ import annotations

import argparse
from pathlib import Path

import joblib
from sentence_transformers import SentenceTransformer

from train import MODEL_PATH


def build_text(statement: str, code: str, verdict: str) -> str:
    return (
        f"Statement:\n{statement}\n\n"
        f"Code:\n{code}\n\n"
        f"Verdict:\n{verdict}"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-path", type=str, default=str(MODEL_PATH))
    parser.add_argument("--statement", type=str, required=True)
    parser.add_argument("--code", type=str, required=True)
    parser.add_argument("--verdict", type=str, required=True)
    args = parser.parse_args()

    model_path = Path(args.model_path)
    bundle = joblib.load(model_path)

    clf = bundle["classifier"]
    le = bundle["label_encoder"]
    embedding_model_name = bundle["embedding_model_name"]

    encoder = SentenceTransformer(embedding_model_name)
    x = encoder.encode(
        [build_text(args.statement, args.code, args.verdict)],
        convert_to_numpy=True,
        show_progress_bar=False,
    )
    pred = clf.predict(x)[0]
    label = le.inverse_transform([pred])[0]
    print(label)


if __name__ == "__main__":
    main()
