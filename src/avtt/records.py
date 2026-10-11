"""Map/scene record writers in Atlas's vault-adoption shapes.

Spec: README §3.1. Records are the JSON files Atlas adopts from
``atlas-vtt/collections/<collectionId>/{maps,scenes,...}/<stem>.json``.

Key facts the writers rely on (all verified against v0.6.0):
- Missing ids are fine — Atlas recovers them deterministically from the
  path (``recoveredIds.ts``), so our stems (site slugs) are the identity.
- A scene record references its content: ``data.mapPath`` points at the
  ``.atlasmap`` file.
- A map record states its image: ``mapFilePath`` (+ optional
  ``thumbnailPath``).
- Minimum shape: ``{id?, name, tags, collection, createdAt, modifiedAt,
  type: '<asset type>'}``; blank name falls back to the prettified stem.
"""

from __future__ import annotations


def map_record(stem: str, map_file_path: str, *,
               name: str = "", thumbnail_path: str = "") -> dict:
    """A ``maps/<stem>.json`` payload (type ``map``)."""
    raise NotImplementedError("lands with the scenes build (ticket 05); README §3.1")


def scene_record(stem: str, atlasmap_vault_path: str, *, name: str = "") -> dict:
    """A ``scenes/<stem>.json`` payload whose ``data.mapPath`` points at
    the converted ``.atlasmap``."""
    raise NotImplementedError("lands with the scenes build (ticket 05); README §3.1")
