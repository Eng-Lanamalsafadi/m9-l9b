"""Linker P/R/F1 scoring."""
from linker.types import LinkResult, GoldSpan


def score(predictions: list[LinkResult], gold: list[GoldSpan]) -> dict:
    """Compute precision, recall, F1 over (node_id, type_label) tuples.

    Triple-stated methodology (verbatim in lab-spec.md, lab guide page, and
    this docstring):

    - Predictions are filtered to the gold span set (same doc_id, start, end)
      before scoring; predictions on spans absent from gold are dropped.
    - A span is a true positive iff the predicted (node_id, type_label)
      EXACTLY matches gold AND gold is non-NIL.
    - A prediction of a wrong (node_id, type_label) on a non-NIL gold is a
      false positive AND a false negative on that span.
    - A NIL prediction on a non-NIL gold is a false negative only.
    - A non-NIL prediction on a NIL gold is a false positive only.
    - A NIL prediction on a NIL gold is a true negative (not counted in
      precision or recall).
    - Aggregation is macro-average across documents (per-doc P/R/F1 averaged
      with equal weight per doc; docs with no gold spans are skipped).

    Returns {'precision': float, 'recall': float, 'f1': float}.
    """
    # TODO:
    # 1. Build a gold-span index keyed by (doc_id, start, end) for fast lookup.
    # 2. Filter predictions to the gold span set per the methodology.
    # 3. For each doc_id in gold, accumulate TP / FP / FN per the rules above
    #    (TN-NIL is informational only — not in P or R).
    # 4. Compute per-doc P, R, F1 (with 0/0 convention: P=R=F1=0 when the
    #    denominator is 0; skip docs with no gold spans entirely).
    # 5. Macro-average the per-doc metrics; return the dict.
    gold_by_doc = {}
    for g in gold:
        gold_by_doc.setdefault(g.doc_id, {})[(g.start, g.end)] = g
        
    pred_by_doc = {}
    for p in predictions:
        pred_by_doc.setdefault(p.doc_id, {})[(p.start, p.end)] = p

    all_doc_ids = set(gold_by_doc.keys())
    
    doc_precisions = []
    doc_recalls = []
    doc_f1s = []
    
    for doc_id in all_doc_ids:
        doc_gold_spans = gold_by_doc[doc_id]
        doc_pred_spans = pred_by_doc.get(doc_id, {})
        
        tp = 0
        fp = 0
        fn = 0
        
        for span, g_span in doc_gold_spans.items():
            p_span = doc_pred_spans.get(span)
            
            gold_node = g_span.gold_node_id
            gold_type = g_span.gold_type_label
            
            pred_node = getattr(p_span, "predicted_node_id", None) if p_span else None
            pred_type = getattr(p_span, "predicted_type_label", None) if p_span else None
            
            if gold_node is not None:
                if pred_node == gold_node and pred_type == gold_type:
                    tp += 1
                elif pred_node is not None:
                    fp += 1
                    fn += 1
                else:
                    fn += 1
            else:
                if pred_node is not None:
                    fp += 1

        p_denom = tp + fp
        r_denom = tp + fn
        
        doc_p = tp / p_denom if p_denom > 0 else 0.0
        doc_r = tp / r_denom if r_denom > 0 else 0.0
        
        if (doc_p + doc_r) > 0:
            doc_f1 = (2 * doc_p * doc_r) / (doc_p + doc_r)
        else:
            doc_f1 = 0.0
            
        doc_precisions.append(doc_p)
        doc_recalls.append(doc_r)
        doc_f1s.append(doc_f1)
        
    if not doc_precisions:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0}
        
    return {
        "precision": sum(doc_precisions) / len(doc_precisions),
        "recall": sum(doc_recalls) / len(doc_recalls),
        "f1": sum(doc_f1s) / len(doc_f1s)
    }