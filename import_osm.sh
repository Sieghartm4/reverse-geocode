#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

# --- CONFIGURATION VARIABLES ---
DB_NAME="ph_geodata"
DB_USER="postgres"
DB_PASSWORD="password1"
DB_HOST="localhost"
CACHE_SIZE="800" # RAM allocation in MB
PBF_FILE="philippines-latest.osm.pbf"
STYLE_FILE="default.style"

# Explicit path to your osm2pgsql executable (Git Bash / POSIX format)
OSM2PGSQL_PATH="/c/Users/dev/Downloads/osm2pgsql-latest-x64/osm2pgsql-bin/osm2pgsql.exe"

echo "===================================================="
echo "Starting OpenStreetMap Import for the Philippines..."
echo "Target Database: $DB_NAME"
echo "Target User:     $DB_USER"
echo "===================================================="

# Check if the PBF file exists before starting
if [ ! -f "$PBF_FILE" ]; then
    echo "Error: File '$PBF_FILE' not found in the current directory."
    exit 1
fi

# Run osm2pgsql using its absolute path variable
export PGPASSWORD="$DB_PASSWORD"
"$OSM2PGSQL_PATH" -d "$DB_NAME" \
          -H "$DB_HOST" \
          -U "$DB_USER" \
          --style "$STYLE_FILE" \
          --slim \
          --drop \
          --hstore \
          --number-processes 4 \
          --flat-nodes flatnodes.bin \
          -C "$CACHE_SIZE" \
          "$PBF_FILE"

echo "===================================================="
echo "Import completed successfully!"
echo "===================================================="