# TAKNET-PS Packaging Checklist

Run through this before every release package. Claude: read this before packaging.

## Required for every release

- [ ] `VERSION` file updated
- [ ] `version.json` — version, release_date, release_notes updated
- [ ] `install/install.sh` — VERSION= string updated to match
- [ ] `README.md` — **Current Version** in header updated
- [ ] `README.md` — **Version Information** section (version, date, changelog bullets) updated

## Verify before tar

```bash
grep "Current Version" README.md
cat VERSION
grep '"version"' version.json
```

All three should agree. (`install.sh` pulls VERSION from the repo at install time — no hardcoded string to update.)

## Package command

```bash
VERSION=$(cat VERSION)
cp -r taknet-ps-v2.58.0 taknet-ps-complete-v${VERSION}-production
tar -czf taknet-ps-complete-v${VERSION}-production.tar.gz taknet-ps-complete-v${VERSION}-production/
```
