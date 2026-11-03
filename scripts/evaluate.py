"""Evaluate a manually labeled JSONL file; prints measured values only."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from prompt_sentinel.config import load_settings
from prompt_sentinel.detector import Detector


def main(path: Path) -> None:
    detector = Detector(load_settings())
    counts = {"tp": 0, "fp": 0, "tn": 0, "fn": 0}
    with path.open(encoding="utf-8") as stream:
        for number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            sample = json.loads(line)
            label = sample["label"]
            if label not in {"attack", "benign"}:
                raise ValueError(f"Line {number}: label must be attack or benign")
            verdict = detector.inspect(sample["text"], sample.get("role", "tool"))
            positive = verdict.action == "block"
            key = "tp" if label == "attack" and positive else (
                "fn" if label == "attack" else ("fp" if positive else "tn")
            )
            counts[key] += 1
            print(f"{number}: expected={label} actual={verdict.action} engines={verdict.engines}")
    tp, fp, tn, fn = (counts[key] for key in ("tp", "fp", "tn", "fn"))
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    false_positive_rate = fp / (fp + tn) if fp + tn else 0.0
    print(f"counts={counts}")
    print(f"precision={precision:.3f} recall={recall:.3f} false_positive_rate={false_positive_rate:.3f}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python scripts/evaluate.py samples/smoke.jsonl")
    main(Path(sys.argv[1]))
