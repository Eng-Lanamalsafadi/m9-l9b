"""Linker orchestrator.

Wires candidates() -> disambiguate() into one pass over the NER spans of
a document, producing one LinkResult per span.
"""
from linker.candidates import candidates
from linker.disambiguate import disambiguate
from linker.types import LinkResult


def link(
    driver,
    doc_id: str,
    text: str,
    ner_spans: list[tuple[int, int, str, str]],
) -> list[LinkResult]:
    """Orchestrate the linker pipeline for one document.

    Args:
      driver: an open neo4j.GraphDatabase driver.
      doc_id: identifier of this document (propagated into every LinkResult).
      text: the document text (currently unused inside the function; reserved
        for future context features — keep the parameter in the signature
        because the Integration repo calls link() with it).
      ner_spans: a list of (start, end, surface, ner_label) tuples in
        document order.

    Returns: list[LinkResult], one per input span, in the same order.

    Iterate in document order so that doc_resolved grows monotonically and
    the co-occurrence signal builds up as the document is walked.
    """
    # TODO:
    # 1. Initialize results = [] and doc_resolved = [].
    # 2. For each (start, end, surface, ner_label) in ner_spans (in order):
    #      a. Call candidates(driver, surface).
    #      b. Call disambiguate(driver, candidates_list, ner_label, doc_resolved).
    #      c. Construct a LinkResult (predicted_node_id/predicted_type_label
    #         from the chosen candidate dict, or None on NIL).
    #      d. Append it to results AND to doc_resolved.
    # 3. Return results.
    # 1. Initialize result trackers
    results: list[LinkResult] = []
    doc_resolved: list[LinkResult] = []

    # 2. Iterate spans in document order to build context monotonically
    for start, end, surface, ner_label in ner_spans:
        # a. Fetch all potential entity node matches
        cands = candidates(driver, surface)
        
        # Build predictions and map reason tokens as required by the pipeline specs
        if not cands:
            res = LinkResult(
                doc_id=doc_id,
                start=start,
                end=end,
                surface=surface,
                predicted_node_id=None,
                predicted_type_label=None,
                reason="nil-no-candidates"
            )
        elif len(cands) == 1:
            res = LinkResult(
                doc_id=doc_id,
                start=start,
                end=end,
                surface=surface,
                predicted_node_id=cands[0]["id"],
                predicted_type_label=cands[0]["labels"][0], # Extract primary domain label
                reason="resolved-unique"
            )
        else:
            # b. Disambiguate when multiple candidates exist
            chosen, reason_token = disambiguate(driver, cands, ner_label, doc_resolved)
            
            # c. Construct the LinkResult with chosen candidate parameters or fallback to NIL
            res = LinkResult(
                doc_id=doc_id,
                start=start,
                end=end,
                surface=surface,
                predicted_node_id=chosen["id"] if chosen else None,
                predicted_type_label=chosen["labels"][0] if chosen else None,
                reason=reason_token
            )
            
        # d. Append to output results and expand context memory window
        results.append(res)
        doc_resolved.append(res)
        
    # 3. Return collection of sequential alignments
    return results