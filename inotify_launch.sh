#!/bin/bash

WATCH_DIR="$(pwd)"
SNAPSHOT_DIR="/tmp/inotify_snapshot"

# Timestamped log file
TIMESTAMP="$(date '+%Y-%m-%d_%H-%M-%S')"
LOG_FILE="$WATCH_DIR/changes_${TIMESTAMP}.log"

# Exclude solver output, meshes, STLs, logs, self-generated diff logs, and hidden/swap files
EXCLUDE_PATTERN='(^|/)(processor[0-9]+|[0-9]+(\.[0-9]+)?|postProcessing|polyMesh|triSurface|extendedFeatureEdgeMesh|\..*|.*\.log|changes_.*)(/|$)'

# Redirect all stdout and stderr to both console and the log file
exec > >(tee -a "$LOG_FILE") 2>&1

echo "================================================="
echo "Change monitor started at $(date '+%Y-%m-%d %H:%M:%S')"
echo "Watching:  $WATCH_DIR"
echo "Log file:  $LOG_FILE"
echo "================================================="

echo "Creating initial snapshot..."
rm -rf "$SNAPSHOT_DIR"
mkdir -p "$SNAPSHOT_DIR"

rsync -a \
  --exclude 'processor[0-9]*/' \
  --exclude '[0-9]*/' \
  --exclude 'postProcessing/' \
  --exclude 'polyMesh/' \
  --exclude 'triSurface/' \
  --exclude 'extendedFeatureEdgeMesh/' \
  --exclude '*.log' \
  --exclude 'changes_*' \
  --exclude '.*' \
  "$WATCH_DIR"/ "$SNAPSHOT_DIR"/

echo "Snapshot stored in: $SNAPSHOT_DIR"
echo "Waiting for changes..."

stdbuf -oL inotifywait -m -r -q \
  --format '%w%f' \
  -e close_write,create,delete,moved_to,moved_from \
  --exclude "$EXCLUDE_PATTERN" \
  "$WATCH_DIR" |
while IFS= read -r FILE; do
    # Skip directories
    [ -d "$FILE" ] && continue

    REL="${FILE#$WATCH_DIR/}"
    OLD="$SNAPSHOT_DIR/$REL"
    NOW="$(date '+%Y-%m-%d %H:%M:%S')"

    # Case 1: Existing file modified
    if [ -f "$FILE" ] && [ -f "$OLD" ]; then
        DIFF_OUT="$(diff -u "$OLD" "$FILE" 2>/dev/null)"
        if [ -n "$DIFF_OUT" ]; then
            echo
            echo "================================================"
            echo "[$NOW] Modified: $REL"
            echo "================================================"
            echo "$DIFF_OUT"
            cp -a "$FILE" "$OLD"
        fi

    # Case 2: New file created
    elif [ -f "$FILE" ] && [ ! -f "$OLD" ]; then
        echo
        echo "================================================"
        echo "[$NOW] New File: $REL"
        echo "================================================"
        if [ ! -s "$FILE" ]; then
            echo "[empty file]"
        else
            diff -u /dev/null "$FILE" | tail -n +3
        fi
        mkdir -p "$(dirname "$OLD")"
        cp -a "$FILE" "$OLD"

    # Case 3: File deleted
    elif [ ! -e "$FILE" ] && [ -f "$OLD" ]; then
        echo
        echo "================================================"
        echo "[$NOW] Deleted: $REL"
        echo "================================================"
        if [ ! -s "$OLD" ]; then
            echo "[empty file was removed]"
        else
            diff -u "$OLD" /dev/null | tail -n +3
        fi
        rm -f "$OLD"
    fi
done
