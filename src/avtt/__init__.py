"""avtt — the Atlas VTT adapter layer.

Everything here writes Atlas-owned file formats or carries system-specific
table data (README §1). The canon core (dnd-campaign-generator) never
imports this package, and this package never imports the core: contract
rule 4, orchestration not integration.

Modules:
    uvtt           .uvtt parsing: fields, Atlas limits, plain-words refusals
    image_headers  stdlib PNG/JPEG/WebP dimension readers
    scene          .uvtt -> .atlasmap conversion (the AGPL-noted port)
    records        map/scene record writers in the vault-adoption shapes
    presets        system-preset pack installer + ported validator
    config         campaign-side config (collection id, pack, paths)
    publish        the CLI that ties it together

Status: skeleton. Every function raises NotImplementedError until its
spike (README §12) and ticket land. README.md is this repo's constitution.
"""

__all__ = [
    "uvtt",
    "image_headers",
    "scene",
    "records",
    "presets",
    "config",
    "publish",
]
