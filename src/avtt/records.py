"""Map/scene record writers in Atlas's vault-adoption shapes.

Spec: README §3.1. Records are the JSON files Atlas adopts from
``atlas-vtt/collections/<collectionId>/{maps,scenes,...}/<stem>.json``.

Key facts the writers rely on (all verified against the pinned release,
``avtt._version.ATLAS_PIN`` — ticket 01/02 spikes, re-checked in the
0.6.0 tree at commit ``c5a99830``):
- Missing ids are fine — Atlas recovers them deterministically from the
  path (``recoveredIds.ts``), so our stems (site slugs) are the identity.
- A scene record references its content: on disk the reference is a
  top-level ``mapPath`` — adoption reads ``payload.mapPath``
  (``assetAdoption.ts``), falling back to the sibling ``<stem>.atlasmap``;
  the ``data: {mapPath}`` shape is the in-memory asset, which Atlas's own
  writer flattens into the file's payload (``recordFile.ts``). Our
  records state the top-level ``mapPath``.
- A map record states its image: ``mapFilePath``, the vault-relative
  path of the image copied beside the record. We omit
  ``thumbnailPath``: adoption ignores the field and Atlas's background
  pass generates thumbnails for maps lacking one (ticket 02, v0.6.0).
- Minimum shape: ``{id?, name, tags, collection, createdAt, modifiedAt,
  type: '<asset type>'}``; blank name falls back to the prettified stem,
  timestamps fall back to adoption time, and ``collection`` always comes
  from the file's folder — so ours carry only the fields that are
  genuinely ours: name, tags, type, and the stated path.
- Atlas rewrites adopted record files in place into a canonical form:
  the payload beside an ``atlasRecord: {format: 1, ...}`` envelope
  (``recordFile.ts``). :func:`matches` compares a record's *meaning*
  against that form, never raw bytes (contract rule 3, ticket 01).
"""

from __future__ import annotations

RECORD_KEY = "atlasRecord"      # recordFile.ts — the envelope Atlas adds when it rewrites a record
RECORD_FORMAT = 1               # recordFile.ts RECORD_FORMAT
# fields the file's place or Atlas's adoption owns; refuse-on-diff ignores them
ATLAS_OWNED_FIELDS = frozenset({"id", "collection", "createdAt", "modifiedAt", "filePath"})


def map_record(stem: str, map_file_path: str, *, name: str = "") -> dict:
    """A ``maps/<stem>.json`` payload (type ``map``).

    ``mapFilePath`` convention (ticket 02, verified against v0.6.0):
    ``map_file_path`` is the vault-relative path of the image copied
    beside this record —
    ``atlas-vtt/collections/<collectionId>/maps/<stem>.png`` — and the
    image must be written before the record: adoption skips a map whose
    stated image is missing. Our records carry no ``thumbnailPath``:
    adoption drops the field, and ``AssetThumbnailService`` generates
    thumbnails in the background for maps lacking one.
    """
    return {"name": name or stem, "tags": [], "type": "map", "mapFilePath": map_file_path}


def scene_record(stem: str, atlasmap_vault_path: str, *, name: str = "") -> dict:
    """A ``scenes/<stem>.json`` payload whose ``mapPath`` points at the
    converted ``.atlasmap`` (the top-level shape adoption reads; see the
    module docstring)."""
    return {"name": name or stem, "tags": [], "type": "scene", "mapPath": atlasmap_vault_path}


def matches(existing: dict, intended: dict) -> bool:
    """Whether an existing record file still means what ``intended`` says.

    The comparison is on meaning, never raw bytes (contract rule 3 as
    sharpened by ticket 01): Atlas rewrites adopted records into the
    ``atlasRecord`` envelope beside the payload, and fields it owns —
    id, collection, timestamps, filePath — drift by design. The fields
    that must match are name, tags, type and the stated path
    (``mapFilePath``/``mapPath``, always at the file's top level in both
    our write and Atlas's rewrite); when an envelope is present it is
    the authoritative statement of them.
    """
    if not isinstance(existing, dict):
        return False
    envelope = existing.get(RECORD_KEY)
    source = envelope if isinstance(envelope, dict) else existing
    for field in ("name", "tags", "type"):
        if source.get(field) != intended.get(field):
            return False
    path_field = "mapFilePath" if intended.get("type") == "map" else "mapPath"
    return existing.get(path_field) == intended.get(path_field)
