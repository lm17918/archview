#!/bin/bash
# Run BEFORE starting archview:
#   ./docs/demo_build.sh
# Then in another terminal:
#   archview example_project --interval 2
#
# This script moves everything out, then restores piece by piece.

DIR="example_project"
STASH="/tmp/archview_demo_stash"
DELAY=3

# Move EVERYTHING out
rm -rf "$STASH"
cp -r "$DIR" "$STASH"
rm -rf "$DIR"
mkdir "$DIR"

echo ">>> example_project is now empty."
echo "    Start 'archview example_project --interval 2' in another terminal."
echo "    Start recording with Peek."
echo "    Press Enter when ready."
read

# 1. main.py alone
cp "$STASH/main.py" "$DIR/"
echo "  + main.py"
sleep $DELAY

# 2. config + utils
cp "$STASH/config.py" "$DIR/"
cp -r "$STASH/utils" "$DIR/"
echo "  + config.py + utils/"
sleep $DELAY

# 3. models
cp -r "$STASH/models" "$DIR/"
echo "  + models/"
sleep $DELAY

# 4. services + api (graph explodes)
cp -r "$STASH/services" "$DIR/"
cp -r "$STASH/api" "$DIR/"
echo "  + services/ + api/"
sleep $DELAY

# 5. everything else
cp -r "$STASH/data" "$DIR/" 2>/dev/null
cp "$STASH/migrate.py" "$DIR/" 2>/dev/null
cp "$STASH/seed_db.py" "$DIR/" 2>/dev/null
cp "$STASH/export_report.py" "$DIR/" 2>/dev/null
cp "$STASH/cleanup.py" "$DIR/" 2>/dev/null
cp "$STASH/.archviewignore" "$DIR/" 2>/dev/null
echo "  + data/ + scripts — full graph!"

echo ""
echo ">>> Done! Full project restored."
rm -rf "$STASH"
