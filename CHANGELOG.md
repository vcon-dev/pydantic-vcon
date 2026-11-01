# Changelog

## 0.1.0

Port to vCon core-05 (`draft-ietf-vcon-vcon-core-05`, syntax `"0.5.0"`). Breaking
for a pre-1.0 release.

### Added
- `Session`, `SessionId`, `SessionReference` (types child, peer, precursor, breakout) and the
  top-level `sessions` array.
- `Event` and the top-level `events` array, with per-type parameter validation (table 4.3.1.5):
  party, key, transfer and `channel-contributors` types. Unknown types are kept as extensions.
- `redacted_from` / `amended_from` (`RedactedFrom`, `AmendedFrom`), `redacted_strings`
  (`RedactedString`), Dialog `redacted_segments` (`RedactedSegments`), `extensions`, `critical`.
- Attachment `session`, and the rule that an Attachment has a party plus a dialog or a session.
- Rule that at least one Session exists when `dialog` or `events` is non-empty.
- Empty Dialog Object `{}` as a placeholder.
- `migrate_0_4_0_to_0_5_0(vcon, strict=False)` returning `(vcon, MigrationReport)`, a port of the
  reference migration (steps T1 to T15). `VCon.from_dict` and `VCon.build_from_json` migrate
  0.4.0 input on read.
- `VCon.check()`, `has_lawful_basis()`, `create_attachment()`, `add_session()`, `add_event()`.
- `CHANGELOG.md`, tests for every Appendix B example (parse, round trip, Appendix C schema),
  model JSON schema checks against Appendix C required fields, and the reference migration cases.

### Changed
- `vcon` is `"0.5.0"` and optional on input. New vCons get a version 8 UUID.
- Dialog types are `recording`, `text`, `incomplete`; other values are accepted as extension
  values. `audio` and `video` are read with a warning and never written.
- Dialog `parties` holds contributors only; receivers live in `Session.parties`.
- Attachment `type` is now `purpose` (`type` is read with a DeprecationWarning). `start` and
  `party` are required, as in Appendix C.
- Analysis gains `sessions`, `attachment`, `analysis`; `encoding` and `body` are no longer required
  together (Appendix C). `schema` is exposed as `schema_` with the JSON name `schema`.
- Dates stay as the string given; `created_at` is no longer converted to `datetime`.
- `add_dialog`, `add_party`, `add_analysis`, `add_attachment` return the new index.
- `add_tag` takes `party`, `dialog`, `session`; the tags attachment is scoped to the only Session
  unless one is given.
- Models accept extra members, so extension parameters survive a round trip.

### Removed
- Dialog types `transfer` and `recording-set` and the Dialog parameters `party_history`,
  `originator`, `transferee`, `transferor`, `transfer_target`, `original`, `consultation`,
  `target_dialog`, `recordings`, `recording_set` (rejected with a message pointing at the migration).
  `PartyHistory` is gone; use `Event`.
- `Redacted` and `Appended` are now aliases of `RedactedFrom` and `AmendedFrom`; the top-level
  `redacted` and `amended` names are read with a DeprecationWarning.
- Party members `role`, `contact_list`, `meta` and Dialog members `campaign`, `interaction_type`,
  `interaction_id`, `skill`, `meta` are no longer declared (not in core-05); they still round-trip
  as extra members.
- The `group` exclusivity check against `redacted_from` / `amended_from` (not in core-05).
- `find_party_by_id`, `find_dialog_by_id`, `find_analysis_by_id`, which referenced attributes that
  did not exist.

### Not covered
- JWS/JWE signing, verification and encryption. The models reject signed and encrypted envelopes
  and say to unwrap them first.

### Lawful basis
The library never adds a `lawful_basis` attachment and the migration never invents one. A
migrated `lawful_basis` attachment keeps its `dialog` scope and the report notes the missing
`session`.
