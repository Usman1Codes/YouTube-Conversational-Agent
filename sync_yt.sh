#!/bin/bash

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Define the source and destination paths
SOURCE_FILE="$SCRIPT_DIR/yt.py"
# Prefer the modern CLI entrypoint if available.
if [ -f "$SCRIPT_DIR/yt_cli.py" ]; then
  SOURCE_FILE="$SCRIPT_DIR/yt_cli.py"
fi
DEST_FILE="/usr/local/bin/yt"

# Check if yt.py exists in the script's directory
if [ ! -f "$SOURCE_FILE" ]; then
    echo "Error: yt.py not found in $SCRIPT_DIR"
    echo "Please make sure sync_yt.sh is in the same directory as yt.py"
    exit 1
fi

echo "Attempting to sync $SOURCE_FILE to $DEST_FILE..."

# Determine additional module files to copy alongside the main script
EXTRA_MODULES=("input_handler.py" "video_extractor.py" "gemini_helpers.py")

# Copy main script
echo "You may be prompted for your password to copy to $DEST_FILE."
sudo cp "$SOURCE_FILE" "$DEST_FILE"

# Check if copy was successful
if [ $? -ne 0 ]; then
    echo "Error: Failed to copy $SOURCE_FILE to $DEST_FILE. Check permissions or sudo access."
    exit 1
fi

# Copy extra modules
for module in "${EXTRA_MODULES[@]}"; do
  if [ -f "$SCRIPT_DIR/$module" ]; then
    sudo cp "$SCRIPT_DIR/$module" "/usr/local/bin/$module"
  fi
done

# Copy .env if exists (non-sensitive environments only; comment out if undesired)
if [ -f "$SCRIPT_DIR/.env" ]; then
  sudo cp "$SCRIPT_DIR/.env" "/usr/local/bin/.env"
fi

# Make the destination file executable (requires sudo)
sudo chmod +x "$DEST_FILE"

# Check if chmod was successful
if [ $? -ne 0 ]; then
    echo "Error: Failed to make $DEST_FILE executable."
    exit 1
fi

echo "$DEST_FILE has been updated and made executable."
echo "You should now be able to run 'yt <youtube_link>' from anywhere."

# Verify the version/identity of the new command if possible (optional)
echo "Verifying the installed script (first few lines):"
if command -v "$DEST_FILE" >/dev/null 2>&1; then
    head -n 3 "$DEST_FILE"
else
    echo "Could not verify $DEST_FILE path directly."
fi

echo "Sync complete!" 