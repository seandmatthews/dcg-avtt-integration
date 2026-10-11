"""Campaign-side configuration: collection id, pack name, paths.

Spec: README §4 (``config.py``) and §5. Read from the campaign's
``campaign.yaml`` or an adjacent file. Spike 1 (ticket 01) verified
folder-only adoption on 0.6.0 and 0.7.1, so the collection id is ours
to choose — a stable write-target slug (e.g. the campaign slug), never
a UI-recorded id: Atlas derives the collection record from the folder
on load.

This repo reads campaign directories and writes only inside
``atlas-vtt/`` (contract rule 1) — config is the read side's whole
surface.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AvttConfig:
    """Everything the publishers need to know about one campaign."""

    campaign_dir: Path
    atlas_dir: Path          # <campaign>/atlas-vtt/
    # The write-target slug under atlas-vtt/collections/. Ours to choose
    # (ticket 01): adoption creates the collection from the folder, so
    # this is never a UI-recorded id — but it must be a stable stem
    # (contract rule 3), and note Atlas rewrites adopted record files
    # into canonical form, so refuse-on-diff compares content, not bytes.
    collection_id: str
    pack_name: str           # e.g. "icrpg"; empty = no pack
    sites_dir: Path          # <campaign>/maps/sites/


def load(campaign_dir: Path) -> AvttConfig:
    """Read the config for one campaign directory.

    Missing/contradictory config is refused with a plain-words message,
    never defaulted silently (fed-or-refused, the family rule).
    """
    raise NotImplementedError("lands with the scenes build (ticket 05); shape fixed by ticket 01")
