# fences/

Statblock fence templates for the ICRPG pack land here: `npc`, `pc`,
`mook` (README §4, §6). Rules they must obey, from README §3.5/§6:

- Body-only ` ```statblock ` fences — at 0.8.0 an inline fence displays
  with no plugin installed (the auto template), but token-link creature
  resolution still needs the plugin (README §3.5, 0.8.0 re-statement);
  and the canon core's frontmatter parser must never see pack-specific
  keys.
- Field vocabulary is ICRPG's (hearts, effort, abilities), display-first;
  the mechanically-live number is the preset's hearts resource.
- Values are the table's house conventions — see `../PACK.md`.
