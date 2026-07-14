#!/usr/bin/env bash

set -e

echo "==============================================="
echo "      Claude Code Complete Uninstaller"
echo "==============================================="
echo

########################################
# Detect npm prefix
########################################

PREFIX=$(npm config get prefix 2>/dev/null || true)
GLOBAL_ROOT=$(npm root -g 2>/dev/null || true)

echo "[INFO] npm prefix      : $PREFIX"
echo "[INFO] npm global root : $GLOBAL_ROOT"
echo

########################################
# Uninstall npm package
########################################

echo "[1/8] Removing npm package..."

npm uninstall -g @anthropic-ai/claude-code >/dev/null 2>&1 || true

########################################
# Remove executable
########################################

echo "[2/8] Removing executable..."

rm -f "$PREFIX/bin/claude" 2>/dev/null || true

########################################
# Remove package directory
########################################

echo "[3/8] Removing package directory..."

rm -rf "$GLOBAL_ROOT/@anthropic-ai/claude-code" 2>/dev/null || true

########################################
# Remove user config
########################################

echo "[4/8] Removing user configs..."

rm -rf ~/.claude
rm -f  ~/.claude.json

########################################
# Remove XDG config/cache
########################################

echo "[5/8] Removing cache/config..."

rm -rf ~/.config/claude
rm -rf ~/.cache/claude
rm -rf ~/.local/share/claude

########################################
# Remove project config
########################################

echo "[6/8] Removing project config..."

find "$PWD" -maxdepth 1 -name ".claude" -exec rm -rf {} \; 2>/dev/null || true
find "$PWD" -maxdepth 1 -name ".mcp.json" -delete 2>/dev/null || true

########################################
# Clean npm cache
########################################

echo "[7/8] Cleaning npm cache..."

npm cache clean --force >/dev/null 2>&1 || true

########################################
# Verify
########################################

echo "[8/8] Verifying..."

echo

if command -v claude >/dev/null 2>&1; then
    echo "❌ claude command still exists:"
    which claude
else
    echo "✅ claude command removed."
fi

echo

echo "Global packages containing 'claude':"
npm list -g --depth=0 2>/dev/null | grep -i claude || echo "None"

echo

echo "Executable:"
which claude 2>/dev/null || echo "Not Found"

echo
echo "==============================================="
echo " Claude Code cleanup finished."
echo "==============================================="