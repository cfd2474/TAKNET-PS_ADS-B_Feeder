# TAKNET-PS Packaging Checklist

Run through this before every release package. See also: **Version Bump SOP** (taknet-ps-version-sop.docx).

## Standard flow: use the version-bump script

**Every version update must produce a complete tar.gz of the entire build.** The script updates all version locations per SOP, verifies them, and builds the tar.gz.

```bash
# From repo root. Optional: release_name, release_notes, update_priority.
./scripts/version-bump.sh NEW_VERSION [release_name] [release_notes] [update_priority]
# Example (default priority 3 = alert only):
./scripts/version-bump.sh 2.59.31 "Short name" "What changed."
# Priority 1 = immediate update, 2 = overnight 02:00, 3 = alert only (default):
./scripts/version-bump.sh 2.59.32 "Security fix" "Critical fix." 1
# USB GPS release is priority 3 (alert only):
./scripts/version-bump.sh 2.59.36 "USB GPS support" "Get coordinates from GPS in setup and Settings." 3
```

**Update priority** (in `version.json`): `1` = feeder updates immediately; `2` = feeder schedules update at 02:00 local; `3` = alert only, user clicks Update (default if omitted).

The script:
1. Updates `install/install.sh` (INSTALLER_VERSION + comment)
2. Writes `VERSION`
3. Updates `version.json` (version, release_date, release_name, release_notes, update_priority)
4. Updates `README.md` (both **Current Version** refs)
5. Prepends `CHANGELOG.md` entry
6. Verifies all three canonical versions match
7. **Builds `ARCHIVE/taknet-ps-complete-vX.XX.XX-production.tar.gz`** (entire repo, no .git). Each run adds a new file; old tar.gz files in ARCHIVE are kept.

Output: new tar.gz in `ARCHIVE/`. Commit and push all changed files including the new ARCHIVE/*.tar.gz; do not delete or replace previous archives.

## Manual checklist (if not using script)

- [ ] `install/install.sh` — `INSTALLER_VERSION="X.XX.XX"` and line 3 comment
- [ ] `VERSION` file — single line, no trailing newline
- [ ] `version.json` — version, release_date (YYYY-MM-DD), release_name, release_notes, update_priority (1/2/3, default 3); validate: `python3 -c "import json; json.load(open('version.json'))"`
- [ ] `README.md` — **Current Version** (header and Version History section)
- [ ] `CHANGELOG.md` — new entry prepended
- [ ] Verify: `grep INSTALLER_VERSION install/install.sh`, `cat VERSION`, `python3 -c "import json; print(json.load(open('version.json'))['version'])"`
- [ ] Build complete tar.gz (full repo, no .git); name: `taknet-ps-complete-vX.XX.XX-production.tar.gz`
