"""Campaign-side configuration: collection id, pack name, paths.

Spec: README §4 (``config.py``) and §5. Read from ``<campaign>/avtt.yaml``,
a file beside ``campaign.yaml`` that the DM authors and this repo only
ever reads (contract rule 1: reading campaign directories is the whole
read side; ``campaign.yaml`` itself stays the core's). Fed-or-refused:
missing or contradictory config is refused with a plain-words message,
never defaulted silently.

Shape (all keys optional except ``collection``)::

    collection: ember-coast        # folder slug under atlas-vtt/collections/
    pack: icrpg                    # pack name under packs/; empty = no pack
    grid:                          # the collection's grid defaults
      unit_type: feet              #   feet | yards | meters | units | custom
      unit_distance: 5             #   game units one rules square spans (> 0)
      measurement_mode: metric     #   metric | abstract
    default_widgets:               # the collection's defaultWidgets
      hpBar: true                  #   (a bar is hidden on new scenes when
      stressBar: false             #    its switch is absent or false)

Spike 1 (ticket 01) verified folder-only adoption on 0.6.0 and 0.7.1,
so the collection id is ours to choose — a stable write-target slug
(e.g. the campaign slug), never a UI-recorded id: Atlas derives the
collection record from the folder on load.

``grid`` and ``default_widgets`` stand in for collection settings this
repo must never read back out of ``atlas-vtt/`` (contract rule 2) and
that may not exist yet on a first publish. Absent ``grid`` means "a
fresh collection's defaults" — the scene file then carries no unit
keys, exactly as Atlas writes it for such a collection; absent
``default_widgets`` means a collection that never set them (HP shown,
the secondary bar hidden — ``sceneVisibility.ts``).
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

CONFIG_FILENAME = "avtt.yaml"
COLLECTION_SLUG = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
GRID_UNIT_TYPES = ("feet", "yards", "meters", "units", "custom")   # collectionSettingsTypes.ts
MEASUREMENT_MODES = ("metric", "abstract")                          # collectionSettingsTypes.ts
DEFAULT_UNIT_DISTANCE = 5   # measurementFormat.ts gridMeasurement's fallback


class ConfigRefused(Exception):
    """Config this repo refuses to run on, with the plain-words reason."""


@dataclass(frozen=True)
class GridDefaults:
    """The collection's grid defaults (Atlas ``CollectionGridDefaults``)."""

    unit_type: str
    unit_distance: float
    measurement_mode: str

    @property
    def unit_scale(self) -> float:
        """Game units one rules square spans — the conversion's
        ``ruleDistance``, the only grid number the light math uses."""
        return self.unit_distance


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
    # The collection's grid defaults; None = a fresh collection's (no
    # unit keys in the scene file, unit_scale 5). Fed, never read back.
    grid: GridDefaults | None = None
    # The collection's defaultWidgets; None = never set (HP shown, the
    # secondary bar hidden on new scenes). Fed, never read back.
    default_widgets: dict[str, bool] | None = None


def config_path(campaign_dir: Path) -> Path:
    """Where a campaign's config lives: ``<campaign>/avtt.yaml``."""
    return Path(campaign_dir) / CONFIG_FILENAME


def load(campaign_dir: Path) -> AvttConfig:
    """Read the config for one campaign directory.

    Missing/contradictory config is refused with a plain-words message,
    never defaulted silently (fed-or-refused, the family rule).
    """
    campaign_dir = Path(campaign_dir)
    path = config_path(campaign_dir)
    if not path.is_file():
        raise ConfigRefused(
            f"no {path} — create it with at least:\n"
            "  collection: <collection-slug>   (the folder under atlas-vtt/collections/ to write)\n"
            "  grid:                            (optional; the collection's grid defaults)")
    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ConfigRefused(f"{path} does not read: {exc}") from exc
    if not isinstance(doc, dict):
        raise ConfigRefused(f"{path} is not a YAML mapping")

    collection = doc.get("collection")
    if not isinstance(collection, str) or not COLLECTION_SLUG.match(collection):
        raise ConfigRefused(
            f"{path}: collection is missing or not a stable slug "
            f"(letters, digits, '-' and '_', starting with a letter or digit) — "
            "it is the folder under atlas-vtt/collections/ everything is written to")

    pack = doc.get("pack", "")
    if pack is None:
        pack = ""
    if not isinstance(pack, str):
        raise ConfigRefused(f"{path}: pack is not a string")

    grid = _load_grid(path, doc.get("grid"))
    widgets = _load_default_widgets(path, doc.get("default_widgets"))
    return AvttConfig(
        campaign_dir=campaign_dir,
        atlas_dir=campaign_dir / "atlas-vtt",
        collection_id=collection,
        pack_name=pack,
        sites_dir=campaign_dir / "maps" / "sites",
        grid=grid,
        default_widgets=widgets,
    )


def _load_grid(path: Path, raw) -> GridDefaults | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ConfigRefused(f"{path}: grid is not a mapping")
    unit_type = raw.get("unit_type")
    if unit_type not in GRID_UNIT_TYPES:
        raise ConfigRefused(f"{path}: grid.unit_type {unit_type!r} is not one of "
                            f"{list(GRID_UNIT_TYPES)}")
    unit_distance = raw.get("unit_distance")
    if not isinstance(unit_distance, (int, float)) or isinstance(unit_distance, bool) \
            or not math.isfinite(unit_distance) or unit_distance <= 0:
        raise ConfigRefused(f"{path}: grid.unit_distance {unit_distance!r} is not a "
                            "number above 0")
    mode = raw.get("measurement_mode")
    if mode not in MEASUREMENT_MODES:
        raise ConfigRefused(f"{path}: grid.measurement_mode {mode!r} is not one of "
                            f"{list(MEASUREMENT_MODES)}")
    return GridDefaults(unit_type=unit_type, unit_distance=float(unit_distance),
                        measurement_mode=mode)


def _load_default_widgets(path: Path, raw) -> dict[str, bool] | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ConfigRefused(f"{path}: default_widgets is not a mapping")
    widgets: dict[str, bool] = {}
    for key, value in raw.items():
        if not isinstance(key, str) or not isinstance(value, bool):
            raise ConfigRefused(f"{path}: default_widgets must map widget names to "
                                f"true/false (bad entry {key!r}: {value!r})")
        widgets[key] = value
    return widgets
