"""Disambiguation: pick a single candidate, or abstain (NIL).

Inputs to disambiguate():
  - candidates_ : the list returned by linker.candidates.candidates()
  - ner_label   : the spaCy NER label of the span (e.g., "ORG", "GPE", "FOOD")
  - doc_resolved: the list of LinkResult records already resolved in this
                  document (in document order). Used for co-occurrence
                  signal — a candidate that connects (1 hop in Cypher) to
                  an already-resolved entity is more likely correct.

Required signals (any subset whose combination cleanly resolves the
candidate set, in priority order):
  (a) Length-1 candidate list -> resolved-unique.
  (b) Type compatibility via NER_LABEL_TO_KG_TYPE -> resolved-by-type
      when exactly one candidate matches the allowed labels.
  (c) Hierarchical type compatibility via [:SUBCLASS_OF*0..] -> e.g.,
      a candidate of label :Cuisine resolves when ner_label is "FOOD"
      because :Cuisine is reachable under the type-compatible umbrella.
      reason token = "resolved-by-hierarchy".
  (d) Co-occurrence with doc_resolved entities via 1-hop Cypher MATCH:
      among the surviving candidates, prefer the one with the highest
      neighbour overlap. reason token = "resolved-by-context".
  (e) None of the above resolve -> (None, "nil-no-candidates") when
      candidates_ is empty, else (None, "nil-ambiguous").

Returns: (chosen_candidate_dict_or_None, reason_token).
"""


# NER label -> set of KG labels that are directly type-compatible.
# Learner extends this table for the full evaluation set; two seed entries
# are provided as exemplars.
NER_LABEL_TO_KG_TYPE: dict[str, set[str]] = {
    "PERSON": {"Author"},
    "ORG": {"Author"},
    # TODO: extend NER_LABEL_TO_KG_TYPE with at minimum the following NER
    # labels used in the dev/test splits: "GPE", "FOOD", "INGREDIENT",
    # "TECHNIQUE". Refer to data/README.md for the gold-span NER
    # label distribution and to the §2.1 schema labels (Recipe, Cuisine,
    # Ingredient, Author, Technique).
    "PERSON": {"Author"},
    "ORG": {"Author"},
    "GPE": {"Cuisine"},
    "FOOD": {"Cuisine", "Ingredient"},
    "INGREDIENT": {"Ingredient"},
    "TECHNIQUE": {"Technique"}
}


def disambiguate(
    driver,
    candidates_: list[dict],
    ner_label: str,
    doc_resolved: list,
) -> tuple[dict | None, str]:
    """Return (chosen_candidate_or_None, reason_token).

    See the module docstring for the required signals and reason tokens.

    Implementation guidance:
      - Handle the trivial cases first (empty list, length-1 list).
      - Apply the NER_LABEL_TO_KG_TYPE filter. If exactly one candidate
        survives, return it with reason "resolved-by-type".
      - For the hierarchical case, the load-bearing Cypher shape is:
            MATCH (c:Entity {id: $cand_id})
            MATCH (c)-[:SUBCLASS_OF*0..]->(ancestor:Entity)
            RETURN collect(labels(ancestor)) AS ancestor_labels
        Then check whether ancestor labels intersect the type-compatible
        set. The "*0.." length means the candidate itself counts as a
        depth-0 ancestor, so a direct match resolves here too.
      - For co-occurrence, MATCH a 1-hop neighbourhood from each candidate
        and count how many doc_resolved node ids appear in it. Highest
        count wins; ties fall through to "nil-ambiguous".
    """
    # TODO:
    # 1. Empty candidates -> return (None, "nil-no-candidates").
    # 2. Length-1 candidates -> return (candidates_[0], "resolved-unique").
    # 3. Apply NER_LABEL_TO_KG_TYPE filter; on exactly one survivor return
    #    (survivor, "resolved-by-type").
    # 4. Apply hierarchical traversal via [:SUBCLASS_OF*0..] over driver;
    #    on exactly one survivor return (survivor, "resolved-by-hierarchy").
    # 5. Apply co-occurrence ranking against doc_resolved;
    #    return (winner, "resolved-by-context") when there is a clear winner.
    # 6. Otherwise return (None, "nil-ambiguous").
    # --- 1. Trivial Cases ---
    if not candidates_:
        return None, "nil-no-candidates"
        
    # Note: If the orchestrator links length-1 candidates before calling disambiguate,
    # we still safely handle it here as demanded by the function requirements.
    if len(candidates_) == 1:
        return candidates_[0], "resolved-unique"

    # Fetch valid target types for the given NER label
    compatible_types = NER_LABEL_TO_KG_TYPE.get(ner_label, set())

    # --- 2. Direct Type Filter ---
    type_filtered_candidates = [
        c for c in candidates_
        if any(lbl in compatible_types for lbl in c["labels"])
    ]
    if len(type_filtered_candidates) == 1:
        return type_filtered_candidates[0], "resolved-by-type"

    # --- 3. Hierarchical Traversal via [:SUBCLASS_OF*0..] ---
    hierarchy_filtered_candidates = []
    
    hierarchy_query = """
    MATCH (c:Entity {id: $cand_id})
    MATCH (c)-[:SUBCLASS_OF*0..]->(ancestor:Entity)
    RETURN collect(labels(ancestor)) AS ancestor_labels
    """
    
    with driver.session() as session:
        for cand in candidates_:
            res = session.run(hierarchy_query, cand_id=cand["id"])
            record = res.single()
            if record:
                # Flatten the collected list of label arrays into a single set
                all_ancestor_labels = {
                    lbl 
                    for labels_list in record["ancestor_labels"] 
                    for lbl in labels_list
                }
                if any(lbl in compatible_types for lbl in all_ancestor_labels):
                    hierarchy_filtered_candidates.append(cand)

    if len(hierarchy_filtered_candidates) == 1:
        return hierarchy_filtered_candidates[0], "resolved-by-hierarchy"

    # --- 4. Co-occurrence Context Filter ---
    # Evaluate candidates that survived previous structural/hierarchy pruning. 
    # If the hierarchy check left us empty-handed, fallback to evaluating all original candidates.
    surviving_candidates = (
        hierarchy_filtered_candidates if hierarchy_filtered_candidates else candidates_
    )
    
    # Extract predicted node IDs from already-resolved LinkResult objects
    resolved_ids = [
        res.predicted_node_id 
        for res in doc_resolved 
        if getattr(res, "predicted_node_id", None) is not None
    ]
    
    if resolved_ids and surviving_candidates:
        context_query = """
        MATCH (c:Entity {id: $cand_id})-[]-(neighbor:Entity)
        WHERE neighbor.id IN $resolved_ids
        RETURN count(neighbor) AS overlap
        """
        
        best_cand = None
        max_overlap = -1
        is_tie = False
        
        with driver.session() as session:
            for cand in surviving_candidates:
                res = session.run(context_query, cand_id=cand["id"], resolved_ids=resolved_ids)
                record = res.single()
                overlap = record["overlap"] if record else 0
                
                if overlap > max_overlap:
                    max_overlap = overlap
                    best_cand = cand
                    is_tie = False
                elif overlap == max_overlap:
                    is_tie = True
                    
        if max_overlap > 0 and not is_tie:
            return best_cand, "resolved-by-context"

    # --- 5. Abstain (Ambiguous) ---
    return None, "nil-ambiguous"