# ADR 0002: Data foundation - attributes, classification, units

Status: accepted (2026-11-08)

## Context

Before the next feature milestones we reviewed the data foundation
("Datengrundlage"): where technical attributes live, how parts are
classified, how attribute values are validated, and how BOM units are
controlled. The old model carried one shared `attributes` JSONB blob per
part, which cannot represent revision-scoped changes.

## Decision

1. **Revision-scoped attributes (hybrid model).** Technical attributes move
   from `parts` to `part_revisions` (JSONB). Parts keep only neutral,
   revision-independent fields (number, name, description, type, class).
   A new revision inherits the attributes of its predecessor, like the BOM.
2. **Hierarchical classification.** `part_classes.parent_id` makes classes
   a tree. Class filters in part search include the whole subtree; unknown
   class codes return 404 instead of an empty list. A newly created class
   can never close a cycle (no children yet), and no re-parenting endpoint
   exists.
3. **Typed attribute definitions.** New table `class_attributes` defines per
   class: key, label, type (string/number/boolean/enum), optional unit,
   required flag, and allowed values for enums. Validation runs on part
   creation; keys without a definition pass through (deliberately lenient
   for legacy/free data), defined keys are strictly validated.
4. **Units master data.** New table `units` with natural key `code` and a
   dimension check (count/length/mass/volume/area/time/other).
   `bom_items.unit` gets a foreign key to it; unknown units are rejected
   with 422 `unknown_unit`.

## Rationale

- Attributes change between revisions (e.g. weight after a design change);
  storing them on the revision keeps released revisions immutable and makes
  the change history complete.
- A class tree mirrors how engineering standards are organized (MECH >
  fastening technology) without a heavy class-system feature.
- Typed definitions give the AI prompt layer and reports predictable
  values while the pass-through policy keeps migration effort low.
- Free-text units in BOMs make quantity aggregation and reports unreliable;
  a small master-data table fixes that with referential integrity.

## Alternatives (rejected)

- Keeping attributes on `parts`: cannot express per-revision technical
  state; conflicts with immutability of released revisions.
- Fully normalized attribute values (EAV tables): joins for every part
  read, higher complexity; JSONB on the revision plus typed definitions
  is a pragmatic middle ground.
- Full class system with versioned classes (like a commercial PLM):
  overkill for a small team; revisit if class definitions need revisioning.

## Consequences

- Breaking API changes: `PartResponse` no longer has `attributes`;
  `RevisionResponse` gains `attributes`. `PartCreate.attributes` is now
  validated and stored on revision 01.
- Migration 0003 copies part-level attributes to every existing revision
  (the old model had one shared set), so no data is lost.
- Undefined attribute keys are accepted and stored; tightening the policy
  later is possible without a schema change.
- Units are referenced by natural key; renaming a unit code is a data
  migration, not a code change.
- Search behavior change: unknown `class_code` is 404 (was empty list).
