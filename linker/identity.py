"""Identity Discipline helpers.

In a property graph, identity is not free the way it is for RDF URIs.
Every KG node must carry a canonical id derived from (label, name) so that
two surface mentions of "orange" resolve to the same node iff they refer
to the same entity. The :Entity uniqueness constraint declared in
data/recipes_kg.cypher enforces this.

`canonical_id` is fully implemented — do not modify. `merge_entity` has
one TODO: produce the parameterized Cypher MERGE statement and bound
parameter dict for the (label, name) pair (gated by the Lab 9B
autograder under Gate 1b).
"""
import re


_SLUG_RE = re.compile(r"[^a-z0-9]+")


def canonical_id(label: str, name: str) -> str:
    """Return the canonical KG id for a (label, name) pair.

    Convention: '<label-lower>:<name-slug>'. Examples:
      canonical_id("Ingredient", "Orange")  -> "ingredient:orange"
      canonical_id("Cuisine", "Sichuan")    -> "cuisine:sichuan"
      canonical_id("Author", "Maria Rossi") -> "author:maria-rossi"

    Ambiguous surface forms get DIFFERENT ids because the label differs:
      canonical_id("Ingredient", "orange") -> "ingredient:orange"
      canonical_id("Cuisine",    "Orange") -> "cuisine:orange"
    """
    slug = _SLUG_RE.sub("-", name.strip().lower()).strip("-")
    return f"{label.strip().lower()}:{slug}"


def merge_entity(label: str, name: str, extra_props: dict | None = None) -> tuple[str, dict]:
    """Build a parameterized Cypher MERGE statement for one entity node.

    Returns (cypher_string, params_dict). The caller invokes
    session.run(cypher_string, **params_dict).

    Required behaviour:
      - The node carries TWO labels: the domain label AND :Entity.
      - The MERGE key is the canonical id from canonical_id(label, name).
      - `name` is always set on the node.
      - Any keys in extra_props are set on the node.

    Example expected return for merge_entity("Ingredient", "ginger", {"category": "spice"}):
      ("MERGE (n:Ingredient:Entity {id: $id}) SET n.name = $name, n.category = $category",
       {"id": "ingredient:ginger", "name": "ginger", "category": "spice"})

    NOTE: the property keys in the SET clause must be a literal Cypher
    identifier list — do NOT pass property names as parameters, only
    property VALUES. The id MUST come through a parameter ($id).
    """
    # TODO (Identity Mapping):
    # 1. Compute the canonical id via canonical_id(label, name).
    # 2. Build the Cypher string with two labels (`:<label>:Entity`),
    #    the parameterized MERGE on `{id: $id}`, and a SET clause that
    #    assigns `n.name = $name` plus one `n.<key> = $<key>` clause per
    #    extra_props key.
    # 3. Build the params dict including id, name, and every extra_props entry.
    # 4. Return (cypher, params).
    # 1. Compute the structural canonical identifier
    ent_id = canonical_id(label, name)
    
    # Initialize parameters with the basic tracking values
    params = {
        "id": ent_id,
        "name": name
    }
    
    # 2. Safely interpolate domain labels and template property anchors
    # Label mapping uses string interpolation securely because they are static developer-defined 
    # system labels (e.g. 'Ingredient'), while user context maps to secure parameter bindings.
    cypher_parts = [
        f"MERGE (n:{label.strip()}:Entity {{id: $id}})",
        "SET n.name = $name"
    ]
    
    # Append dynamic extra properties into literal identifier sequences
    if extra_props:
        for key, value in extra_props.items():
            cypher_parts.append(f"n.{key} = ${key}")
            params[key] = value
            
    # 3. Join structural statement tokens together
    cypher_string = " ".join(cypher_parts)
    
    # 4. Return the constructed Cypher and parameter bindings
    return cypher_string, params