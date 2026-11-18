"""Rule and semantic similarity detectors for untrusted text."""

from __future__ import annotations

import re
from threading import Lock
from dataclasses import asdict, dataclass
from typing import Protocol

from .config import Settings


class DetectionUnavailable(RuntimeError):
    """Raised when an enabled detector cannot inspect a request."""


class SemanticScorer(Protocol):
    def score(self, text: str) -> float: ...


class SentenceSemanticScorer:
    def __init__(self, model_name: str, examples: tuple[str, ...]) -> None:
        self.model_name = model_name
        self.examples = examples
        self._model = None
        self._example_vectors = None
        self._load_lock = Lock()

    def score(self, text: str) -> float:
        try:
            if self._model is None:
                with self._load_lock:
                    if self._model is None:
                        from sentence_transformers import SentenceTransformer

                        model = SentenceTransformer(self.model_name)
                        examples = model.encode(list(self.examples), normalize_embeddings=True)
                        self._example_vectors = examples
                        self._model = model
            # Short overlapping windows prevent a long tool result from hiding a payload
            # beyond the embedding model's token limit.
            chunks = [text[start : start + 320] for start in range(0, len(text), 240)] or [""]
            vectors = self._model.encode(chunks, normalize_embeddings=True)
            return max(
                sum(float(a) * float(b) for a, b in zip(chunk, example))
                for chunk in vectors
                for example in self._example_vectors
            )
        except Exception as exc:
            raise DetectionUnavailable("Semantic detector is unavailable") from exc


@dataclass(frozen=True)
class Verdict:
    action: str
    role: str
    engines: tuple[str, ...]
    rule_ids: tuple[str, ...]
    similarity: float | None
    char_count: int
    strategy: str = "both"
    checked_engines: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return asdict(self)


class Detector:
    def __init__(self, settings: Settings, semantic_scorer: SemanticScorer | None = None) -> None:
        self.settings = settings
        self.rules = [(rule.id, re.compile(rule.pattern)) for rule in settings.rules]
        self.semantic_scorer = semantic_scorer
        if settings.semantic_enabled and self.semantic_scorer is None:
            if not settings.semantic_examples:
                raise ValueError("Enabled semantic detector requires examples")
            self.semantic_scorer = SentenceSemanticScorer(
                settings.semantic_model, settings.semantic_examples
            )

    def inspect(self, text: str, role: str = "tool") -> Verdict:
        if role not in {"user", "tool"}:
            raise ValueError("Only user and tool messages can be inspected")
        if len(text) > self.settings.max_chars:
            return Verdict("block", role, ("length_limit",), (), None, len(text), self.settings.strategy)
        order = ("regex", "semantic") if self.settings.strategy == "regex_first" else ("semantic", "regex")
        rule_ids = ()
        similarity = None
        engines = []
        checked = []
        for stage in order:
            if stage == "semantic":
                if not self.settings.semantic_enabled:
                    continue
                if self.semantic_scorer is None:
                    raise DetectionUnavailable("Semantic detector is unavailable")
                score = self.semantic_scorer.score(text)
                similarity = round(score, 4)
                checked.append("semantic")
                if score >= self.settings.semantic_threshold:
                    engines.append("semantic")
            else:
                rule_ids = tuple(rule_id for rule_id, pattern in self.rules if pattern.search(text))
                checked.append("regex")
                if rule_ids:
                    engines.append("regex")
            if engines and self.settings.strategy != "both":
                break
        return Verdict(
            "block" if engines else "allow",
            role,
            tuple(engines),
            rule_ids,
            similarity,
            len(text),
            self.settings.strategy,
            tuple(checked),
        )
