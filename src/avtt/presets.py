"""System-preset pack installer + the ported preset validator.

Spec: README §3.4/§5.2. Presets are plain files at
``atlas-vtt/system-presets/<name>.json``, watched live by Atlas
(``presetFiles.ts``) and validated on load. An invalid preset is
silently ignored by Atlas — the worst failure mode — so the installer
refuses to write anything Atlas would not use exactly as authored.

The validator is a port of Atlas VTT at the pinned release
(``avtt._version.ATLAS_PIN`` — the machine handle; the README §7 table
is the human record): ``presetValidation.ts``
plus the modules it reads through — ``diceRules.ts``, ``diceSets.ts``
(the dice-set group shape of ``defaultRoll``, 0.8.0),
``initiativeRules.ts``, ``lightPresetValidation.ts``,
``senseValidation.ts``, ``visionDefaults.ts``,
``resources/resourceDefinitions.ts``, ``grid/measurementFormat.ts``,
``utils/clockWidget.ts``, ``utils/hexColor.ts``, ``vision/visionCone.ts``,
``types/systemPresetTypes.ts`` and the icon-name keys of
``types/widgetIcons.ts``. Cited, never vendored (AGENTS.md);
``fixtures/golden-{ATLAS_PIN}/`` is the pin's source of truth.
Re-clone and re-check the tag before changing a pinned constant.

Strictness (README §3.4 + ticket 04): Atlas's loader either refuses the
whole preset (fatal — the file is silently ignored) or silently
*drops/repairs* individual knobs (a bad widget entry vanishes, an
out-of-range light radius is clamped). Both are the same failure at the
table — a knob the DM believes is live but is not — so
:func:`validate_preset` refuses both: a preset passes only when Atlas
uses every authored knob as written. It never rejects anything Atlas
would accept verbatim.

The write obeys contract rule 3: refuse-on-diff at
``system-presets/<stem>.json``; ``--force`` writes a ``<stem>-v2``
sibling instead of overwriting. Atlas keys presets by the ``id``
inside the file, never the path (``presetFiles.ts``), and keeps the
first file per id in path order (``RecordFiles.entries`` over
``holders``: every record path, UTF-16 code-unit sort, extension
included — so ``icrpg-v2.json`` sorts *before* ``icrpg.json``, and a
same-id ``-v2`` sibling, not the original, is the live one; re-read at
0.8.0, ticket 11). A same-id file sorting before the target would make
the pack's file inert — a knob the DM believes is live but is not — so
:func:`install` refuses the shadowed write; one sorting after the
target is dead weight and only draws a warning.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

PRESET_FILE_FORMAT = 1
BUILT_IN_ID_PREFIX = "builtin:"
SYSTEM_PRESETS_DIRNAME = "system-presets"

# The systems Atlas ships at 0.8.0, as ``system:`` slugs: the keys of
# ``builtInPresetId(key)`` = ``builtin:`` + key (``builtInPresets.ts`` and
# the ``presets/*.ts`` each file names). Re-verified 2026-10-20 against tag
# 0.8.0 (commit ``3d68221``) — the same ten files as at 0.7.1, and
# ``builtInPresets.ts`` itself unchanged between the tags (ticket 09's
# source diff). Note the odd spellings are Atlas's own ids:
# ``coc7e``, ``cyberpunkred``, ``drawsteel``, ``pathfinder2e``.
BUILTIN_SYSTEMS_0_8_0 = frozenset({
    "cairn", "coc7e", "cyberpunkred", "daggerheart", "dnd5e",
    "drawsteel", "ose", "pathfinder2e", "shadowdark",
})

# Display names for the short-circuit message (each preset's ``name``).
BUILTIN_DISPLAY_NAMES_0_8_0 = {
    "cairn": "Cairn",
    "coc7e": "Call of Cthulhu",
    "cyberpunkred": "Cyberpunk RED",
    "daggerheart": "Daggerheart",
    "dnd5e": "D&D 5e",
    "drawsteel": "Draw Steel",
    "ose": "Old-School Essentials",
    "pathfinder2e": "Pathfinder 2e",
    "shadowdark": "Shadowdark",
}

# --- vocabularies of the pinned release (one line of source each) --------

UNIT_TYPES = ("feet", "yards", "meters", "units", "custom")  # presetValidation.ts
MEASUREMENT_MODES = ("metric", "abstract")
DIAGONAL_RULES = ("equidistant", "alternating", "euclidean")
CONDITION_EFFECTS = ("blinded", "invisible", "airborne", "undetected")  # collectionSettingsTypes.ts
CRIT_RULES = ("natural", "roll-under", "doubles", "high-total", "none")  # diceRules.ts
EXPLODE_SCOPES = ("default", "all")
MAX_EXPLODING_FACES = 99
INITIATIVE_MODES = ("turn-order", "sides")  # initiativeRules.ts
INITIATIVE_SIDES = ("players", "opponents")
LIGHT_ANIMATIONS = ("none", "torch", "candle", "pulse", "magic")  # lightPresetValidation.ts
LIGHT_UNITS = ("feet", "yards", "meters", "squares")
LIGHT_KINDS = ("candle", "torch", "lantern", "magical", "darkness", "custom")  # lightPresets.ts
MAX_INTENSITY = 2  # "the ranges the light popover's sliders give intensity and softness"
MAX_SOURCE_RADIUS = 5
SENSE_BRIGHT = ("none", "normal")  # senseValidation.ts
SENSE_DIM = ("none", "normal", "as-bright")
SENSE_DARK = ("none", "as-dim", "as-bright")
SENSE_LOOKS = ("colour", "monochrome", "black-and-white", "heat")
SENSE_RANGES = ("unlimited", "required", "optional")
SENSE_ROLES = ("darkvision", "tremorsense")
NORMAL_SIGHT_ID = "sight"  # senses/generic.ts NORMAL_SIGHT — reserved, never a listed sense
# senses/generic.ts GENERIC_SENSES — what a collection falls back to
GENERIC_SENSE_IDS = frozenset({
    "darkvision", "low-light-vision", "blindsight", "tremorsense", "truesight", "see-invisible",
})
MIN_CLOCK_SEGMENTS = 2  # utils/clockWidget.ts
MAX_CLOCK_SEGMENTS = 12
# grid/unitDistance.ts MIN_UNIT_DISTANCE / MAX_UNIT_DISTANCE (0.7.1): the
# inclusive range ``isUnitDistance`` accepts. 0.7.1 presetValidation.ts:59
# routes ``gridDefaults.unitDistance`` through it; outside the range
# ``parseGridDefaults`` returns null and Atlas refuses the whole preset.
# (0.6.0 accepted any number > 0 — the tightening is unannounced in the
# changelog; ticket 08's source diff caught it. The source comments the
# minimum: below a millionth JavaScript writes the number as a power of
# ten — "1e-7" — which no field reads back.) Cited, never vendored.
MIN_UNIT_DISTANCE = 0.000001
MAX_UNIT_DISTANCE = 1_000_000
MAX_RESOURCES = 6  # resources/resourceTypes.ts
# the keys of WIDGET_ICON_PATHS (types/widgetIcons.ts) — a condition's badge glyph
WIDGET_ICONS = frozenset({
    "heart", "heartbeat", "health-potion", "skull", "terror", "brain", "strength",
    "crossed-swords", "sword", "shield", "guard", "magic", "spellbook", "lightning",
    "flame", "snowflake", "drop", "potion", "poison", "star", "clover", "crown",
    "prayer", "wings", "eye", "coins", "gem", "key", "hourglass", "stopwatch",
    "campfire", "torch", "rations", "footprints", "moon", "sun", "dragon", "wolf",
    "ghost", "d20", "d6", "scroll", "blindfold", "hearing-disabled", "grab",
    "knockout", "knocked-out-stars", "invisible", "frozen-body", "stoned-skull",
    "foot-trip", "imprisoned", "sleepy", "tired-eye", "hidden", "cracked-shield",
    "surprised", "meditation", "spider-web", "run", "falling", "fog",
    "spiral-bloom", "puppet", "grim-reaper", "life-tap", "weight", "arm-sling",
    "vomiting", "snail", "brain-freeze", "hood", "bleeding-wound", "broken-bone",
    "bleeding-eye", "brain-tentacle", "psychic-waves", "screaming",
})

_HEX_COLOR = re.compile(r"^#[0-9a-f]{6}$", re.IGNORECASE)  # utils/hexColor.ts
# diceRules.ts DEFAULT_ROLL: "1 to 99 dice of 2 to 999 sides"
_DEFAULT_ROLL = re.compile(r"^([1-9]\d?)?d([2-9]|[1-9]\d{1,2})$", re.IGNORECASE)


class PresetRefused(Exception):
    """A preset the installer refuses, with the plain-words reason."""


# --- shape helpers mirroring the TS guards -------------------------------

def _is_record(value) -> bool:
    """TS ``isRecord``: an object, but never an array."""
    return isinstance(value, dict)


def _is_str(value) -> bool:
    return isinstance(value, str)


def _non_empty_str(value) -> bool:
    """TS ``isNonEmptyString``: a string with something after trimming."""
    return isinstance(value, str) and value.strip() != ""


def _number(value) -> bool:
    """TS ``isNumber``: a finite number (a bool is not a number)."""
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _positive(value) -> bool:
    """utils/numberInput.ts ``positiveNumber``: finite and above 0."""
    return _number(value) and value > 0


def _integer(value) -> bool:
    """TS ``Number.isInteger`` (a bool is not an integer)."""
    return isinstance(value, int) and not isinstance(value, bool)


def _default_roll_ok(value) -> bool:
    return isinstance(value, str) and _DEFAULT_ROLL.match(value.strip()) is not None


def _roll_groups_ok(value) -> bool:
    """0.8.0 diceSets.ts ``parseRollGroups`` (diceSets.ts:60): whitespace
    stripped, split on ``+``, **every** part a full match of the same
    ``NdS`` group regex as ``diceRules.ts`` ``DEFAULT_ROLL``
    (``GROUP``, diceSets.ts:54 — the identical pattern), at least one
    group. No group-count cap: ``parseRollGroups`` has none
    (``MAX_SET_GROUPS`` belongs to dice-set editing, not the validator).
    Cited, never vendored (AGENTS.md). Gates ``rules.dice.defaultRoll``
    only (``presetValidation.ts:128``); the initiative roll still goes
    through the single-group ``isValidDefaultRoll``
    (``initiativeRules.ts:23``) — the asymmetry is Atlas's."""
    if not isinstance(value, str):
        return False
    parts = re.sub(r"\s+", "", value).split("+")
    return bool(parts) and all(_DEFAULT_ROLL.match(part) is not None for part in parts)


# --- the validator port ---------------------------------------------------
#
# Each _validate_* mirrors one parse function of the pinned
# presetValidation.ts. Fatal failures (Atlas ignores the whole file) are
# worded as such; everything else is a knob Atlas would silently drop,
# reset or clamp — refused for the same reason.

def validate_preset(preset: dict) -> list[str]:
    """Return the list of validation failures (empty = Atlas uses every knob as written).

    A port of Atlas's ``presetValidation.ts`` checks at the pinned
    version — see the module docstring for the strictness contract.
    """
    failures: list[str] = []
    if not _is_record(preset):
        failures.append("the preset is not a JSON object — Atlas ignores the file")
        return failures
    if not _non_empty_str(preset.get("id")):
        failures.append("id is missing, blank, or not a string — Atlas ignores the file")
    elif preset["id"].startswith(BUILT_IN_ID_PREFIX):
        failures.append(f"id starts with '{BUILT_IN_ID_PREFIX}' — that prefix is "
                        "reserved for Atlas's built-in presets; Atlas ignores the file")
    if not _non_empty_str(preset.get("name")):
        failures.append("name is missing, blank, or not a string — Atlas ignores the file")
    rules = preset.get("rules")
    if not _is_record(rules):
        failures.append("rules is missing or not an object — Atlas ignores the file")
        return failures

    _validate_grid_defaults(rules.get("gridDefaults"), failures)
    conditions = rules.get("conditions")
    if not isinstance(conditions, list):
        failures.append("rules.conditions is missing or not a list — "
                        "Atlas refuses the whole preset without it")
    else:
        _validate_conditions(conditions, failures)
    _validate_widgets(rules.get("widgets"), failures)
    _validate_default_widgets(rules.get("defaultWidgets"), failures)
    _validate_dice(rules.get("dice"), failures)
    _validate_initiative(rules.get("initiative"), failures)
    sense_ids = _validate_senses(rules.get("senses"), failures)
    _validate_resources(rules.get("resources"), failures)
    _validate_vision_defaults(rules.get("defaultTokenVision"), sense_ids, failures)
    _validate_light_presets(rules.get("lightPresets"), failures)
    return failures


def _validate_grid_defaults(raw, failures: list[str]) -> None:
    """``parseGridDefaults`` — every check here is fatal for the whole preset."""
    where = "rules.gridDefaults"
    if not _is_record(raw):
        failures.append(f"{where} is missing or not an object — "
                        "Atlas refuses the whole preset without it")
        return
    if not (_is_str(raw.get("unitType")) and raw["unitType"] in UNIT_TYPES):
        failures.append(f"{where}.unitType {raw.get('unitType')!r} is not one of "
                        f"{list(UNIT_TYPES)} — Atlas refuses the whole preset")
    if not (_is_str(raw.get("measurementMode")) and raw["measurementMode"] in MEASUREMENT_MODES):
        failures.append(f"{where}.measurementMode {raw.get('measurementMode')!r} is not one "
                        f"of {list(MEASUREMENT_MODES)} — Atlas refuses the whole preset")
    if not (_number(raw.get("unitDistance"))
            and MIN_UNIT_DISTANCE <= raw["unitDistance"] <= MAX_UNIT_DISTANCE):
        failures.append(f"{where}.unitDistance {raw.get('unitDistance')!r} is not a "
                        "number between 0.000001 and 1000000 — Atlas refuses the whole preset")
    if raw.get("diagonalRule") is not None and not (
            _is_str(raw["diagonalRule"]) and raw["diagonalRule"] in DIAGONAL_RULES):
        failures.append(f"{where}.diagonalRule {raw['diagonalRule']!r} is not one of "
                        f"{list(DIAGONAL_RULES)} — Atlas would silently substitute 'equidistant'")
    if raw.get("coneAngle") is not None and not (
            _number(raw["coneAngle"]) and 0 < raw["coneAngle"] <= 360):
        failures.append(f"{where}.coneAngle {raw['coneAngle']!r} is not a number in "
                        "(0, 360] — Atlas would silently drop it")
    bands = raw.get("abstractRangeBands")
    if bands is None:
        return
    if not isinstance(bands, list):
        failures.append(f"{where}.abstractRangeBands is not a list — Atlas would silently ignore it")
        return
    for i, band in enumerate(bands):
        # parseBand: name must be a string, maxSquares an integer ≥ 1
        # (isValidRangeBandThreshold); one bad band kills the whole preset.
        if not (_is_record(band) and _is_str(band.get("name"))
                and _integer(band.get("maxSquares")) and band["maxSquares"] >= 1):
            failures.append(f"{where}.abstractRangeBands[{i}] is not a {{name, maxSquares}} "
                            "pair with a whole-number threshold ≥ 1 — Atlas refuses the "
                            "whole preset over one bad band")


def _validate_conditions(conditions: list, failures: list[str]) -> None:
    """``parseCondition``: a bad entry is silently dropped, not fatal."""
    for i, cond in enumerate(conditions):
        where = f"rules.conditions[{i}]"
        if not _is_record(cond):
            failures.append(f"{where} is not an object — Atlas would silently drop this condition")
            continue
        if not _non_empty_str(cond.get("id")):
            failures.append(f"{where}.id is missing or blank — "
                            "Atlas would silently drop this condition")
        if not _is_str(cond.get("name")):
            failures.append(f"{where}.name is missing or not a string — "
                            "Atlas would silently drop this condition")
        if not (_is_str(cond.get("color")) and _HEX_COLOR.match(cond["color"])):
            failures.append(f"{where}.color {cond.get('color')!r} is not a #rrggbb color — "
                            "Atlas would silently drop this condition")
        icon = cond.get("icon")
        if icon is not None and not (_is_str(icon) and icon in WIDGET_ICONS):
            failures.append(f"{where}.icon {icon!r} is not a known widget icon — "
                            "Atlas would silently strip it from this condition")
        effect = cond.get("effect")
        if effect is not None and effect not in CONDITION_EFFECTS + ("none",):
            failures.append(f"{where}.effect {effect!r} is not one of "
                            f"{list(CONDITION_EFFECTS + ('none',))} — Atlas would silently drop it")


def _validate_widgets(widgets, failures: list[str]) -> None:
    """``parseWidget``: a bad widget (or field) vanishes silently."""
    if widgets is None:
        return
    if not isinstance(widgets, list):
        failures.append("rules.widgets is not a list — Atlas would silently ignore it")
        return
    for i, widget in enumerate(widgets):
        where = f"rules.widgets[{i}]"
        if not _is_record(widget):
            failures.append(f"{where} is not an object — Atlas would silently drop this widget")
            continue
        usable = _non_empty_str(widget.get("id")) and _is_str(widget.get("label")) \
            and _number(widget.get("value"))
        wtype = widget.get("type")
        if wtype == "timer":
            usable = usable and _number(widget.get("duration")) and widget["duration"] > 0
        elif wtype == "clock":
            segments = widget.get("segments")
            usable = usable and _integer(segments) \
                and MIN_CLOCK_SEGMENTS <= segments <= MAX_CLOCK_SEGMENTS \
                and 0 <= widget["value"] <= segments
        elif wtype == "counter":
            usable = usable and (
                widget.get("min") is None or _number(widget["min"])) and (
                widget.get("max") is None or _number(widget["max"]))
        else:
            usable = False
        if not usable:
            failures.append(f"{where} ({wtype!r}) is not a usable counter/timer/clock — "
                            "Atlas would silently drop it (a timer needs a duration > 0; "
                            f"a clock needs whole-number segments {MIN_CLOCK_SEGMENTS}–"
                            f"{MAX_CLOCK_SEGMENTS} and a value within them)")
            continue
        icon = widget.get("icon")
        if icon is not None and not (_is_str(icon) and icon in WIDGET_ICONS):
            failures.append(f"{where}.icon {icon!r} is not a known widget icon — "
                            "Atlas would silently show the default 'star' instead")
        if widget.get("order") is not None and not _number(widget["order"]):
            failures.append(f"{where}.order {widget['order']!r} is not a number — "
                            "Atlas would silently reset it to 0")
        if widget.get("color") is not None and not _is_str(widget["color"]):
            failures.append(f"{where}.color is not a string — Atlas would silently drop it")


def _validate_default_widgets(raw, failures: list[str]) -> None:
    """``parseEnabledFlags``: only ``true`` entries mean anything; the rest read as off."""
    if raw is None:
        return
    if not _is_record(raw):
        failures.append("rules.defaultWidgets is not an object — Atlas would silently ignore it")


def _validate_dice(raw, failures: list[str]) -> None:
    """``parseDiceRules``: an unusable section is silently omitted."""
    if raw is None:
        return
    usable = _is_record(raw) and _roll_groups_ok(raw.get("defaultRoll")) \
        and raw.get("crit") in CRIT_RULES
    if not usable:
        failures.append(f"rules.dice is not usable (a defaultRoll like '1d20' or "
                        f"'1d20+1d6' — one or more groups of 1 to 99 dice of 2 to "
                        f"999 sides — and crit one of {list(CRIT_RULES)}) — "
                        "Atlas would silently ignore the whole section")
        return
    explode = raw.get("explode")
    if explode is not None and not (
            _is_record(explode)
            and explode.get("dice") in EXPLODE_SCOPES
            and isinstance(explode.get("repeats"), bool)
            and _integer(explode.get("highFaces")) and 1 <= explode["highFaces"] <= MAX_EXPLODING_FACES
            and _integer(explode.get("lowFaces")) and 0 <= explode["lowFaces"] <= MAX_EXPLODING_FACES):
        failures.append(f"rules.dice.explode is not usable (dice one of {list(EXPLODE_SCOPES)}, "
                        "a boolean repeats, and whole-number face counts 1–99 high / 0–99 low) — "
                        "Atlas would silently drop it")


def _validate_initiative(raw, failures: list[str]) -> None:
    """``parseInitiativeRules``: an unusable section is silently omitted."""
    if raw is None:
        return
    if not (_is_record(raw)
            and raw.get("mode") in INITIATIVE_MODES
            and raw.get("firstSide") in INITIATIVE_SIDES
            and _default_roll_ok(raw.get("roll"))):
        failures.append(f"rules.initiative is not usable (mode one of {list(INITIATIVE_MODES)}, "
                        f"firstSide one of {list(INITIATIVE_SIDES)}, a valid roll) — "
                        "Atlas would silently ignore the whole section")


def _validate_senses(raw, failures: list[str]) -> frozenset[str] | None:
    """``parseSenseDefinition``/``parseSenseDefinitions``; returns the ids that
    survive (empty list stays an empty list, matching JS truthiness), or
    None when the section is absent or would be ignored."""
    if raw is None:
        return None
    if not isinstance(raw, list):
        failures.append("rules.senses is not a list — Atlas would silently ignore it "
                        "(its collections fall back to the generic senses)")
        return None
    seen_ids: set[str] = set()
    seen_roles: set[str] = set()
    kept: set[str] = set()
    for i, sense in enumerate(raw):
        where = f"rules.senses[{i}]"
        if not _is_record(sense):
            failures.append(f"{where} is not an object — Atlas would silently drop this sense")
            continue
        if not _non_empty_str(sense.get("id")):
            failures.append(f"{where}.id is missing or blank — Atlas would silently drop this sense")
            continue
        if sense["id"] == NORMAL_SIGHT_ID:
            failures.append(f"{where}.id is '{NORMAL_SIGHT_ID}' — reserved for normal sight, "
                            "Atlas would silently drop this sense")
            continue
        if not _non_empty_str(sense.get("name")):
            failures.append(f"{where}.name is missing or blank — Atlas would silently drop this sense")
            continue
        if sense["id"] in seen_ids:
            failures.append(f"{where}.id {sense['id']!r} repeats an earlier sense — "
                            "Atlas keeps only the first")
            continue
        seen_ids.add(sense["id"])
        grants = sense.get("grants")
        if grants is not None and grants != "see-invisible":
            failures.append(f"{where}.grants {grants!r} — only 'see-invisible' is known; "
                            "Atlas would silently ignore it")
        if grants == "see-invisible":
            # granting(): a modifier carries only id, name and description
            extra = [k for k in ("sees", "look", "reveals", "precise", "seesInvisible",
                                 "worksWhileBlinded", "range", "defaultRange", "ignores",
                                 "role", "lineOfSight") if k in sense]
            if extra:
                failures.append(f"{where} grants 'see-invisible' — a modifier sense keeps only "
                                f"id, name and description; Atlas ignores {', '.join(extra)}")
            kept.add(sense["id"])
            continue
        if sense.get("description") is not None and not _is_str(sense["description"]):
            failures.append(f"{where}.description is not a string — Atlas would silently reset it to ''")
        sees = sense.get("sees")
        if sees is not None:
            if not _is_record(sees):
                failures.append(f"{where}.sees is not an object — Atlas would silently "
                                "reset its sight fields to 'none'")
            else:
                for field, options in (("bright", SENSE_BRIGHT), ("dim", SENSE_DIM),
                                       ("dark", SENSE_DARK), ("magicalDark", SENSE_DARK)):
                    if sees.get(field) is not None and sees[field] not in options:
                        failures.append(f"{where}.sees.{field} {sees[field]!r} is not one of "
                                        f"{list(options)} — Atlas would silently reset it to 'none'")
        look = sense.get("look")
        if look is not None and look not in SENSE_LOOKS:
            failures.append(f"{where}.look {look!r} is not one of {list(SENSE_LOOKS)} — "
                            "Atlas would silently reset it to 'colour'")
        if sense.get("reveals") == "all" and sense.get("lineOfSight") is False:
            failures.append(f"{where} sets reveals 'all' with lineOfSight false — "
                            "Atlas would silently reset it to 'creatures' (walls must stop "
                            "a sense that shows the map)")
        if sense.get("range") is not None and sense["range"] not in SENSE_RANGES:
            failures.append(f"{where}.range {sense['range']!r} is not one of "
                            f"{list(SENSE_RANGES)} — Atlas would silently reset it to 'required'")
        if sense.get("defaultRange") is not None and not _positive(sense["defaultRange"]):
            failures.append(f"{where}.defaultRange {sense['defaultRange']!r} is not a number "
                            "above 0 — Atlas would silently drop it")
        ignores = sense.get("ignores")
        if ignores is not None and ignores != "airborne":
            failures.append(f"{where}.ignores {ignores!r} — only 'airborne' is known; "
                            "Atlas would silently drop it")
        role = sense.get("role")
        if role is not None:
            if role not in SENSE_ROLES:
                failures.append(f"{where}.role {role!r} is not one of {list(SENSE_ROLES)} — "
                                "Atlas would silently drop it")
            elif role in seen_roles:
                failures.append(f"{where}.role {role!r} is already given to an earlier "
                                "sense — Atlas strips it here (one sense per role)")
            else:
                seen_roles.add(role)
        kept.add(sense["id"])
    return kept


def _validate_resources(raw, failures: list[str]) -> None:
    """``parseResourceDefinitions``: bad entries dropped, later duplicates dropped,
    only the first MAX_RESOURCES kept."""
    if raw is None:
        return
    if not isinstance(raw, list):
        failures.append("rules.resources is not a list — Atlas would silently fall back "
                        "to a plain HP bar, ignoring the whole section")
        return
    seen: set[str] = set()
    for i, res in enumerate(raw):
        where = f"rules.resources[{i}]"
        if not _is_record(res):
            failures.append(f"{where} is not an object — Atlas would silently drop this resource")
            continue
        usable = (_non_empty_str(res.get("key")) and _non_empty_str(res.get("name"))
                  and _non_empty_str(res.get("field"))
                  and res.get("direction") in ("drains", "fills", "static")
                  and _is_str(res.get("color")) and _HEX_COLOR.match(res["color"]))
        if not usable:
            failures.append(f"{where} needs a non-blank key/name/field, a direction of "
                            "drains/fills/static, and a #rrggbb color — Atlas would "
                            "silently drop it")
            continue
        if res.get("key") in seen:
            failures.append(f"{where}.key {res['key']!r} repeats an earlier resource — "
                            "Atlas keeps only the first")
            continue
        seen.add(res["key"])
        slot = res.get("slot")
        if slot is not None and not (_integer(slot) and 0 <= slot < MAX_RESOURCES):
            failures.append(f"{where}.slot {slot!r} is not a whole number 0–"
                            f"{MAX_RESOURCES - 1} — Atlas would silently drop it")
        if res.get("defeatedWhenSpent") is True and res["direction"] == "static":
            failures.append(f"{where} sets defeatedWhenSpent on a 'static' resource — "
                            "a static value is never spent, Atlas would silently ignore the flag")
    if len(raw) > MAX_RESOURCES:
        failures.append(f"rules.resources lists {len(raw)} resources — Atlas keeps at most "
                        f"{MAX_RESOURCES} and silently drops the rest")


def _validate_vision_defaults(raw, sense_ids: frozenset[str] | None, failures: list[str]) -> None:
    """``parseVisionDefaults`` + ``parseTokenSenses``: entries not in the preset's
    own senses (or the generic set) are silently dropped; the old darkvision /
    tremorsense numbers are read only while NO senses list is present — a list
    replaces them even when it is empty (``parseTokenSenses`` returns ``[]``,
    and an empty JS array is truthy, so ``senses ? [] : OLD_SENSE_FIELDS``
    skips the old fields; Atlas's own test:
    ``parseVisionDefaults({darkvision: 60, tremorsense: 30, senses: []})``
    → undefined)."""
    if raw is None:
        return
    if not _is_record(raw):
        failures.append("rules.defaultTokenVision is not an object — Atlas would silently ignore it")
        return
    where = "rules.defaultTokenVision"
    known = sense_ids if sense_ids is not None else GENERIC_SENSE_IDS
    before = len(failures)
    used = False

    if raw.get("range") is not None:
        if _positive(raw["range"]):
            used = True
        else:
            failures.append(f"{where}.range {raw['range']!r} is not a number above 0 — "
                            "Atlas would silently drop it")
    if raw.get("angle") is not None:
        angle = raw["angle"]
        if _number(angle) and 1 <= angle < 360:
            used = True
        elif _number(angle) and 0 < angle < 1:
            failures.append(f"{where}.angle {angle!r} is below 1 — Atlas would silently "
                            "round it up to 1")
        else:
            failures.append(f"{where}.angle {angle!r} — a vision cone is a positive number "
                            "below 360; Atlas would silently drop it")

    senses_list = raw.get("senses")
    used_senses: list[str] = []
    if senses_list is not None:
        if not isinstance(senses_list, list):
            failures.append(f"{where}.senses is not a list — Atlas would silently ignore it "
                            "(the legacy darkvision/tremorsense fields are read instead)")
        else:
            seen: set[str] = set()
            for i, entry in enumerate(senses_list):
                spot = f"{where}.senses[{i}]"
                if not (_is_record(entry) and _non_empty_str(entry.get("id"))):
                    failures.append(f"{spot} has no usable id — Atlas would silently drop it")
                    continue
                if entry["id"] in seen:
                    failures.append(f"{spot}.id {entry['id']!r} repeats an earlier entry — "
                                    "Atlas keeps only the first")
                    continue
                if entry["id"] not in known:
                    failures.append(f"{spot} names sense {entry['id']!r}, which this preset "
                                    "does not define (and is not a generic sense) — Atlas "
                                    "would silently drop it")
                    continue
                seen.add(entry["id"])
                if entry.get("range") is not None and not _positive(entry["range"]):
                    failures.append(f"{spot}.range {entry['range']!r} is not a number above 0 — "
                                    "Atlas would silently drop it")
                used_senses.append(entry["id"])
            if used_senses:
                used = True
            # A present list replaces the legacy fields even when it is empty
            # or every entry was dropped (truthy [] in JS).
            for old in ("darkvision", "tremorsense"):
                if old in raw:
                    failures.append(f"{where}.{old} is ignored because a senses list is "
                                    "present — the list replaces the old fields, empty "
                                    "or not")
    if senses_list is None or not isinstance(senses_list, list):
        # no senses list at all (absent, or a value that is no list):
        # the old fields are read instead
        for old in ("darkvision", "tremorsense"):
            if old in raw:
                if _positive(raw[old]):
                    used = True
                else:
                    failures.append(f"{where}.{old} {raw[old]!r} is not a number above 0 — "
                                    "Atlas would silently drop it")

    if not used and len(failures) == before:
        failures.append(f"{where} sets nothing Atlas would use — the whole section is ignored")


def _validate_light_presets(raw, failures: list[str]) -> None:
    """``parseLightPreset``: bad entries dropped; distances without a known unit
    dropped; bright clamped to dim; unknown color/animation/kind replaced."""
    if raw is None:
        return
    if not isinstance(raw, list):
        failures.append("rules.lightPresets is not a list — Atlas would silently ignore it")
        return
    seen: set[str] = set()
    for i, light in enumerate(raw):
        where = f"rules.lightPresets[{i}]"
        if not _is_record(light):
            failures.append(f"{where} is not an object — Atlas would silently drop this light")
            continue
        if not _non_empty_str(light.get("id")):
            failures.append(f"{where}.id is missing or blank — Atlas would silently drop this light")
            continue
        if not _non_empty_str(light.get("name")):
            failures.append(f"{where}.name is missing or blank — Atlas would silently drop this light")
            continue
        if light["id"] in seen:
            failures.append(f"{where}.id {light['id']!r} repeats an earlier light — "
                            "Atlas keeps only the first")
            continue
        seen.add(light["id"])
        if not (_number(light.get("dim")) and light["dim"] > 0):
            failures.append(f"{where}.dim {light.get('dim')!r} is not a number above 0 — "
                            "a light without reach is dropped by Atlas")
            continue
        bright = light.get("bright")
        if bright is not None:
            if not _number(bright):
                failures.append(f"{where}.bright {bright!r} is not a number — "
                                "Atlas would silently reset it to 0")
            elif bright < 0:
                failures.append(f"{where}.bright {bright!r} is negative — "
                                "Atlas would silently clamp it to 0")
            elif bright > light["dim"]:
                failures.append(f"{where}.bright {bright!r} is past dim {light['dim']!r} — "
                                "Atlas would silently clamp it to dim (a light never reaches "
                                "past its dim radius)")
        if light.get("unit") is not None and light["unit"] not in LIGHT_UNITS:
            failures.append(f"{where}.unit {light['unit']!r} is not one of {list(LIGHT_UNITS)} — "
                            "Atlas would silently drop it (the light reads in the "
                            "collection's own units)")
        color = light.get("color")
        if color is not None and not (_is_str(color) and _HEX_COLOR.match(color)):
            failures.append(f"{where}.color {color!r} is not a #rrggbb color — "
                            "Atlas would silently replace it with white")
        if light.get("animation") is not None and light["animation"] not in LIGHT_ANIMATIONS:
            failures.append(f"{where}.animation {light['animation']!r} is not one of "
                            f"{list(LIGHT_ANIMATIONS)} — Atlas would silently reset it to 'none'")
        if light.get("kind") is not None and light["kind"] not in LIGHT_KINDS:
            failures.append(f"{where}.kind {light['kind']!r} is not one of {list(LIGHT_KINDS)} — "
                            "Atlas would silently reset it to 'custom'")
        radius = light.get("sourceRadius")
        if radius is not None:
            if not _number(radius):
                failures.append(f"{where}.sourceRadius {radius!r} is not a number — "
                                "Atlas would silently drop it")
            elif not 0 <= radius <= MAX_SOURCE_RADIUS:
                failures.append(f"{where}.sourceRadius {radius!r} is outside 0–"
                                f"{MAX_SOURCE_RADIUS} — Atlas would silently clamp it")
        intensity = light.get("intensity")
        if intensity is not None:
            if not _number(intensity):
                failures.append(f"{where}.intensity {intensity!r} is not a number — "
                                "Atlas would silently drop it")
            elif not 0 <= intensity <= MAX_INTENSITY:
                failures.append(f"{where}.intensity {intensity!r} is outside 0–"
                                f"{MAX_INTENSITY} — Atlas would silently clamp it")
        if light.get("angle") is not None:
            angle = light["angle"]
            if _number(angle) and 1 <= angle < 360:
                pass
            elif _number(angle) and 0 < angle < 1:
                failures.append(f"{where}.angle {angle!r} is below 1 — Atlas would silently "
                                "round it up to 1")
            else:
                failures.append(f"{where}.angle {angle!r} — a light cone is a positive number "
                                "below 360; Atlas would silently drop it")
        priority = light.get("priority")
        if priority is not None and not _number(priority):
            failures.append(f"{where}.priority {priority!r} is not a number — "
                            "Atlas would silently drop it")


# --- the pack and the installer -------------------------------------------

def packs_root() -> Path:
    """The repo's ``packs/`` directory (this file lives at ``src/avtt/presets.py``)."""
    return Path(__file__).resolve().parents[2] / "packs"


def load_preset_file(path: Path) -> dict:
    """Read and JSON-decode one preset file (a JSON object, or PresetRefused)."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise PresetRefused(f"cannot read {path}: {exc}") from exc
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise PresetRefused(f"{path} does not parse as JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise PresetRefused(f"{path} is not a JSON object")
    return payload


def pack_preset_path(pack: str) -> Path:
    """Where a pack's preset lives: ``packs/<pack>/preset.json``."""
    return packs_root() / pack / "preset.json"


def load_pack_preset(pack: str) -> dict:
    """Load and JSON-decode ``packs/<pack>/preset.json``."""
    if not pack or Path(pack).name != pack or pack in {".", ".."}:
        raise PresetRefused(f"invalid pack name {pack!r} — expected a plain folder name under packs/")
    path = pack_preset_path(pack)
    if not path.is_file():
        raise PresetRefused(f"no pack '{pack}' — expected {path}")
    return load_preset_file(path)


def preset_payload(payload: dict) -> dict:
    """The file as Atlas itself writes it (``presetFiles.ts presetText``):
    the ``format`` key leads, then the preset as stored."""
    written: dict = {"format": PRESET_FILE_FORMAT}
    written.update({k: v for k, v in payload.items() if k != "format"})
    return written


def _preset_body(payload: dict) -> dict:
    return {k: v for k, v in payload.items() if k != "format"}


def target_state(atlas_dir: Path, stem: str, payload: dict) -> str:
    """``'missing' | 'same' | 'differs'`` for
    ``<atlas_dir>/system-presets/<stem>.json`` against ``payload``.

    The comparison is on the parsed preset body, ignoring the ``format``
    envelope key — Atlas does not rewrite preset files behind us (unlike
    adopted records, ticket 01), so like-for-like means like-for-like.
    """
    target = atlas_dir / SYSTEM_PRESETS_DIRNAME / f"{stem}.json"
    if not target.exists():
        return "missing"
    try:
        existing = load_preset_file(target)
    except PresetRefused:
        return "differs"
    return "same" if _preset_body(existing) == _preset_body(preset_payload(payload)) else "differs"


def _carried_id(path: Path) -> str | None:
    """The id ``path`` carries, or None when it carries no preset.

    Mirrors ``readRecordText`` (``recordFolder.ts``): a file only holds
    a preset when it parses to a JSON object whose ``id`` is a non-blank
    string outside the ``builtin:`` prefix — anything else holds no
    record (``RecordFiles`` keeps a ``null`` for it) and cannot shadow
    anything.
    """
    try:
        payload = load_preset_file(path)
    except (PresetRefused, OSError, ValueError):
        # not JSON / not UTF-8 / unreadable — no id, no shadow; a
        # UnicodeDecodeError from read_text is a ValueError load_preset_file
        # does not wrap, and a foreign file must never crash the scan.
        return None
    preset_id = payload.get("id")
    if not _non_empty_str(preset_id) or preset_id.startswith(BUILT_IN_ID_PREFIX):
        return None
    return preset_id


def same_id_siblings(presets_dir: Path, target_name: str,
                     preset_id: str) -> tuple[list[str], list[str]]:
    """Other preset files under ``presets_dir`` carrying ``preset_id``,
    as ``(shadows, dead_weight)`` — paths relative to ``presets_dir``
    in POSIX form, each list sorted by the order Atlas enumerates.

    That order is the one ``RecordFiles.holders`` uses: every record
    path in byte order, extension included, and the folder is read
    recursively with a case-insensitive ``.json`` check
    (``recordFolder.ts`` ``isRecordPath``, ``RecordFiles.readFolder``) —
    so the scan walks subfolders too, not just siblings beside the
    target. ``shadows`` are the same-id files sorting *before*
    ``target_name`` (Atlas reads the first of them and ignores the
    target); ``dead_weight`` those sorting after (inert now, live again
    the day the target is removed). A missing ``presets_dir`` holds
    nothing.
    """
    shadows: list[str] = []
    dead_weight: list[str] = []
    if not presets_dir.is_dir():
        return shadows, dead_weight
    target_key = target_name.encode("utf-8")
    for path in presets_dir.rglob("*"):
        if not path.is_file() or not path.name.lower().endswith(".json"):
            continue
        relative = path.relative_to(presets_dir).as_posix()
        if relative == target_name or _carried_id(path) != preset_id:
            continue
        listed = shadows if relative.encode("utf-8") < target_key else dead_weight
        listed.append(relative)
    shadows.sort(key=lambda name: name.encode("utf-8"))
    dead_weight.sort(key=lambda name: name.encode("utf-8"))
    return shadows, dead_weight


def shadowed_write_reason(target_name: str, shadow: str, preset_id: str) -> str:
    """The plain-words refusal for the shadowed write (ticket 11)."""
    return (f"not writing {target_name}: {shadow} already carries id {preset_id} and "
            "sorts first, so Atlas would keep reading it — delete or rename the old "
            "file, or edit it by hand")


def dead_weight_note(name: str, preset_id: str, target_name: str) -> str:
    """The one-line warning for a same-id file sorting after the target."""
    return (f"warning: {name} carries the same id {preset_id!r} and sorts after "
            f"{target_name} — Atlas reads {target_name} and ignores it, but it becomes "
            f"live again if {target_name} is ever removed; delete it by hand")


def install(preset_path: Path, atlas_dir: Path, *, stem: str, force: bool = False,
            warnings: list[str] | None = None) -> Path:
    """Validate a preset file, then copy it to
    ``<atlas_dir>/system-presets/<stem>.json``.

    Refuse-on-diff (contract rule 3): a target that exists and differs is
    never overwritten — ``--force`` writes a ``<stem>-v2`` sibling
    instead, leaving the original in place (Atlas keys presets by the id
    inside the file, so the sibling is a real second copy, not a rename).
    The sibling itself is refuse-on-diff too: ``--force`` twice in a row
    on a moved table ends in a refusal, not a clobber.

    The shadowed-write check (ticket 11): once the effective target is
    known — plain stem, or the ``-v2`` sibling after ``--force`` — any
    other file under ``system-presets/`` carrying the same id and
    sorting before it is the one Atlas reads (first file per id), so
    the target would be inert; the install refuses, nothing written,
    even when the target already matches (a "success" for a file Atlas
    will never read is the failure this check exists to kill). A
    same-id file sorting after the target is dead weight: the install
    proceeds and appends one plain-words line per file to ``warnings``
    (when given) for the caller to print.

    Returns the path that holds the pack's preset after the call —
    written now, or the identical file already there. Raises
    PresetRefused with a plain-words reason when anything refuses,
    before anything is written.
    """
    payload = load_preset_file(preset_path)
    failures = validate_preset(payload)
    if failures:
        raise PresetRefused(f"{preset_path} would not survive Atlas's own loader — "
                            "refusing to install (an invalid preset is silently ignored "
                            "there): " + "; ".join(failures))
    presets_dir = atlas_dir / SYSTEM_PRESETS_DIRNAME
    target = presets_dir / f"{stem}.json"
    state = target_state(atlas_dir, stem, payload)
    if state == "differs" and not force:
        raise PresetRefused(f"{target} exists and differs — nothing was overwritten "
                            f"(contract rule 3); rerun with --force to write a "
                            f"'{stem}-v2' sibling beside it")
    if state == "differs" and force:
        sibling = presets_dir / f"{stem}-v2.json"
        sibling_state = target_state(atlas_dir, f"{stem}-v2", payload)
        if sibling_state == "differs":
            raise PresetRefused(f"{sibling} exists and differs too — resolve by hand; "
                                "nothing was written")
        target = sibling
        state = sibling_state
    shadows, dead_weight = same_id_siblings(presets_dir, target.name, payload["id"])
    if shadows:
        raise PresetRefused(shadowed_write_reason(target.name, shadows[0], payload["id"]))
    if warnings is not None:
        for name in dead_weight:
            warnings.append(dead_weight_note(name, payload["id"], target.name))
    if state == "same":
        return target
    presets_dir.mkdir(parents=True, exist_ok=True)
    written = preset_payload(payload)
    target.write_text(json.dumps(written, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return target
