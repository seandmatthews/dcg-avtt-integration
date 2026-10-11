"""Ticket 02's spike decisions, pinned where the publisher will read them.

The record writers' bodies land with the scenes build (ticket 05); until
then the mapFilePath convention and the thumbnail answer live in
``records.map_record``'s docstring (and this file keeps them there).
"""

from __future__ import annotations

import inspect

from avtt import records


def test_map_record_docstring_states_map_file_path_convention():
    """Ticket 02: the image is copied beside the record at
    ``maps/<stem>.png`` and the record states its vault-relative path —
    the convention the ticket 05 publisher must follow."""
    doc = records.map_record.__doc__ or ""
    assert "atlas-vtt/collections/<collectionId>/maps/<stem>.png" in doc
    assert "mapFilePath" in doc


def test_map_record_docstring_rules_out_supplied_thumbnails():
    """Ticket 02 (v0.6.0): adoption drops ``thumbnailPath`` and Atlas's
    background pass generates thumbnails for maps lacking one, so our
    records never carry one — the docstring says so."""
    doc = records.map_record.__doc__ or ""
    assert "no ``thumbnailPath``" in doc


def test_map_record_takes_no_thumbnail_parameter():
    """The stub surface carries the decision: there is no ``thumbnail_path``
    argument left to misuse (removed with ticket 02's finding)."""
    params = inspect.signature(records.map_record).parameters
    assert "thumbnail_path" not in params
