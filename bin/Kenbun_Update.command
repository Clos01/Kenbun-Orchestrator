#!/usr/bin/env bash
# ==============================================================================
# 🍎 Kenbun macOS 1-Click Desktop Launcher
# Double-click this file in Finder to pull updates & activate all sovereign tools
# ==============================================================================

# Ensure we run from the Kenbun repository root
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${DIR}"

# Run the synchronizer
"${DIR}/bin/mac-sync"

# Keep the window open so the developer can see the results
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
read -n 1 -s -r -p "✨ Sync finished. Press any key to close this terminal... "
echo ""
exit 0
