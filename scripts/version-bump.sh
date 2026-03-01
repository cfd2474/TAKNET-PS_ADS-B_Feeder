#!/usr/bin/env bash
# TAKNET-PS Version Bump & Package Script
# Follows Version Bump SOP: updates all locations, verifies, builds complete tar.gz.
# Usage: ./scripts/version-bump.sh NEW_VERSION [release_name] [release_notes]
# Example: ./scripts/version-bump.sh 2.59.30 "Tailscale universal tailnet" "Tailscale status and SSH work for any tailnet."
# If release_name/release_notes omitted, defaults are used.

set -e

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

if [ -z "$1" ]; then
    echo "Usage: $0 NEW_VERSION [release_name] [release_notes]"
    echo "Example: $0 2.59.30 \"Short release name\" \"What changed.\""
    exit 1
fi

NEW_VERSION="$1"
RELEASE_NAME="${2:-Release v$NEW_VERSION}"
RELEASE_NOTES="${3:-See CHANGELOG.md for details.}"
RELEASE_DATE="$(date +%Y-%m-%d)"

# Validate version format X.Y.Z
if ! [[ "$NEW_VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo "Error: Version must be X.Y.Z (e.g. 2.59.30)"
    exit 1
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  TAKNET-PS Version Bump → $NEW_VERSION"
echo "  Date: $RELEASE_DATE"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# 1. install/install.sh — INSTALLER_VERSION and comment
echo "1. Updating install/install.sh..."
sed -i.bak "s/^INSTALLER_VERSION=.*/INSTALLER_VERSION=\"$NEW_VERSION\"/" install/install.sh
sed -i.bak "s/One-Line Installer v[0-9.]*/One-Line Installer v$NEW_VERSION/" install/install.sh
rm -f install/install.sh.bak

# 2. VERSION file
echo "2. Updating VERSION..."
echo -n "$NEW_VERSION" > VERSION

# 3. version.json (pass args via env to avoid shell escaping issues)
echo "3. Updating version.json..."
export _VB_VERSION="$NEW_VERSION" _VB_DATE="$RELEASE_DATE" _VB_NAME="$RELEASE_NAME" _VB_NOTES="$RELEASE_NOTES"
python3 << 'PYEOF'
import os, json
p = "version.json"
with open(p) as f:
    j = json.load(f)
j["version"] = os.environ["_VB_VERSION"]
j["release_date"] = os.environ["_VB_DATE"]
j["release_name"] = os.environ["_VB_NAME"]
j["release_notes"] = os.environ["_VB_NOTES"]
with open(p, "w") as f:
    json.dump(j, f, indent=2)
    f.write("\n")
PYEOF
unset _VB_VERSION _VB_DATE _VB_NAME _VB_NOTES

# 4. README.md — both Current Version refs
echo "4. Updating README.md..."
sed -i.bak "s/\*\*Current Version: [0-9.]*\*\*/\*\*Current Version: $NEW_VERSION\*\*/" README.md
sed -i.bak "s/\*\*Current Version:\*\* [0-9.]*/\*\*Current Version:\*\* $NEW_VERSION/" README.md
rm -f README.md.bak

# 5. CHANGELOG.md — prepend new entry
echo "5. Updating CHANGELOG.md..."
CHANGELOG_ENTRY="## v$NEW_VERSION — $RELEASE_DATE

### Changed
- $RELEASE_NOTES

---
"
if [ -f CHANGELOG.md ]; then
    echo "$CHANGELOG_ENTRY$(cat CHANGELOG.md)" > CHANGELOG.md
else
    echo "$CHANGELOG_ENTRY" > CHANGELOG.md
fi

# 6. Verify all three canonical locations match
echo ""
echo "6. Verifying version sync..."
INSTALL_VER=$(grep '^INSTALLER_VERSION=' install/install.sh | sed 's/.*"\(.*\)"/\1/')
FILE_VER=$(cat VERSION)
JSON_VER=$(python3 -c "import json; print(json.load(open('version.json'))['version'])")
if [ "$INSTALL_VER" != "$NEW_VERSION" ] || [ "$FILE_VER" != "$NEW_VERSION" ] || [ "$JSON_VER" != "$NEW_VERSION" ]; then
    echo "Error: Version mismatch after update!"
    echo "  install.sh: $INSTALL_VER"
    echo "  VERSION:    $FILE_VER"
    echo "  version.json: $JSON_VER"
    exit 1
fi
echo "   install.sh:   $INSTALL_VER"
echo "   VERSION:      $FILE_VER"
echo "   version.json: $JSON_VER"
echo "   ✓ All match."

# Validate version.json syntax
python3 -c "import json; json.load(open('version.json')); print('   ✓ version.json valid')"

# 7. Build complete tar.gz into ARCHIVE/ (keep all versions; do not delete/replace old)
echo ""
echo "7. Building complete tar.gz..."
mkdir -p "$REPO_ROOT/ARCHIVE"
ARCHIVE_NAME="taknet-ps-complete-v${NEW_VERSION}-production"
TMP_DIR=$(mktemp -d)
trap "rm -rf '$TMP_DIR'" EXIT
mkdir -p "$TMP_DIR/$ARCHIVE_NAME"
rsync -a --exclude='.git' --exclude='*.tar.gz' --exclude='.cursor' --exclude='*.bak' "$REPO_ROOT/" "$TMP_DIR/$ARCHIVE_NAME/"
tar -czf "$REPO_ROOT/ARCHIVE/${ARCHIVE_NAME}.tar.gz" -C "$TMP_DIR" "$ARCHIVE_NAME"
rm -rf "$TMP_DIR"
trap - EXIT

TAR_PATH="$REPO_ROOT/ARCHIVE/${ARCHIVE_NAME}.tar.gz"
SIZE=$(ls -lh "$TAR_PATH" | awk '{print $5}')
echo "   Created: $TAR_PATH ($SIZE)"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Version bump complete: $NEW_VERSION"
echo "  Next: commit and push (include ARCHIVE/*.tar.gz); each release adds a new tar.gz, old ones are kept."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
