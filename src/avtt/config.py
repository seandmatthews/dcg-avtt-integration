"""Campaign-side configuration: collection id, pack name, paths.

Spec: README §4 (``config.py``) and §5. Read from the campaign's
``campaign.yaml`` or an adjacent file — the exact home is spike 1's
output (README §12.1): if folder-only collections are adopted, no
collection id needs configuring; if not, the id recorded once in the
Atlas UI lands here.

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
    collection_id: str | None  # None until spike 1 decides it is needed
    pack_name: str           # e.g. "icrpg"; empty = no pack
    sites_dir: Path          # <campaign>/maps/sites/


def load(campaign_dir: Path) -> AvttConfig:
    """Read the config for one campaign directory.

    Missing/contradictory config is refused with a plain-words message,
    never defaulted silently (fed-or-refused, the family rule).
    """
    raise NotImplementedError("lands with the scenes build (ticket 05); shape set by spike 1 (ticket 01)")
