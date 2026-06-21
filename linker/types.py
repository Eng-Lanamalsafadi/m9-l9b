"""Shared dataclasses for the linker.

Fully implemented — do not modify. The Integration repo imports these
types via the function signatures in linker/link.py and linker/score.py.
"""
from dataclasses import dataclass



@dataclass(frozen=True)
class GoldSpan:
    """A gold-annotated NER span with its expected KG identity.

    Attributes:
      doc_id: identifier of the document this span belongs to.
      start: character offset (inclusive) of the span in the document text.
      end: character offset (exclusive) of the span.
      surface: the surface text of the span (the literal substring).
      gold_node_id: canonical KG node id, or None for NIL (no candidate).
      gold_type_label: KG label such as "Ingredient" or "Cuisine"; None when NIL.
    """
    doc_id: str
    start: int
    end: int
    surface: str
    gold_node_id: str | None
    gold_type_label: str | None


@dataclass(frozen=True)
class LinkResult:
    """A linker prediction for one NER span.

    Attributes:
      doc_id: identifier of the document this span belongs to.
      start: character offset (inclusive) of the span in the document text.
      end: character offset (exclusive) of the span.
      surface: the surface text of the span.
      predicted_node_id: predicted KG node id, or None for NIL.
      predicted_type_label: KG label of the predicted node; None when NIL.
      reason: one of "resolved-unique" | "resolved-by-type" |
        "resolved-by-context" | "resolved-by-hierarchy" |
        "nil-no-candidates" | "nil-ambiguous".
    """
    doc_id: str
    start: int
    end: int
    surface: str
    predicted_node_id: str | None
    predicted_type_label: str | None
    reason: str
