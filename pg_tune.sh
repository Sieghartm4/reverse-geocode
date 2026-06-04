#!/usr/bin/env bash
# pg_tune.sh — Apply PostgreSQL tuning for the reverse geocoder
# Usage:  bash pg_tune.sh
# Requires: psql installed, run as a user with superuser access to Postgres

set -e  # stop on first error

# ── Config — edit these to match your setup ───────────────────────────────────
DB_NAME="${DB_NAME:-ph_geodata}"
DB_USER="${DB_USER:-postgres}"
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"

# Load from .env if present (same folder as app.py)
if [ -f .env ]; then
  export $(grep -v '^#' .env | xargs)
fi

PSQL="psql -U $DB_USER -h $DB_HOST -p $DB_PORT -d $DB_NAME"

echo ""
echo "======================================================"
echo " PostgreSQL tuning — reverse geocoder"
echo " Target: $DB_USER@$DB_HOST:$DB_PORT/$DB_NAME"
echo "======================================================"
echo ""

# ── Step 1: Check current values ─────────────────────────────────────────────
echo ">>> Current settings:"
$PSQL -c "
SELECT name, setting, unit, context
FROM pg_settings
WHERE name IN (
    'shared_buffers', 'effective_cache_size', 'work_mem',
    'max_connections', 'random_page_cost', 'maintenance_work_mem'
)
ORDER BY name;
"

# ── Step 2: Apply settings (each runs outside a transaction) ─────────────────
echo ""
echo ">>> Applying settings..."

$PSQL -c "ALTER SYSTEM SET shared_buffers       = '2GB';"
echo "  shared_buffers       = 2GB"

$PSQL -c "ALTER SYSTEM SET effective_cache_size = '6GB';"
echo "  effective_cache_size = 6GB"

$PSQL -c "ALTER SYSTEM SET work_mem             = '64MB';"
echo "  work_mem             = 64MB"

$PSQL -c "ALTER SYSTEM SET maintenance_work_mem = '512MB';"
echo "  maintenance_work_mem = 512MB"

$PSQL -c "ALTER SYSTEM SET random_page_cost     = '1.1';"
echo "  random_page_cost     = 1.1  (SSD — change to 4.0 for HDD)"

$PSQL -c "ALTER SYSTEM SET max_connections      = '100';"
echo "  max_connections      = 100"

# ── Step 3: Reload config (applies everything except shared_buffers + max_connections) ──
echo ""
echo ">>> Reloading config..."
$PSQL -c "SELECT pg_reload_conf();"

# ── Step 4: ANALYZE ───────────────────────────────────────────────────────────
echo ""
echo ">>> Running ANALYZE on OSM tables (may take a few minutes)..."
$PSQL -c "ANALYZE planet_osm_polygon;"
echo "  planet_osm_polygon done"
$PSQL -c "ANALYZE planet_osm_line;"
echo "  planet_osm_line    done"
$PSQL -c "ANALYZE planet_osm_point;"
echo "  planet_osm_point   done"

# ── Step 5: Verify spatial indexes ───────────────────────────────────────────
echo ""
echo ">>> Checking spatial indexes:"
$PSQL -c "
SELECT indexname, tablename
FROM pg_indexes
WHERE indexname IN (
    'idx_osm_line_way',
    'idx_osm_point_way',
    'idx_osm_polygon_way'
);
"

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo "======================================================"
echo " Done."
echo ""
echo " IMPORTANT: shared_buffers and max_connections need a"
echo " full PostgreSQL restart to take effect."
echo ""
echo " Linux:   sudo systemctl restart postgresql"
echo " Windows: net stop postgresql-x64-16"
echo "          net start postgresql-x64-16"
echo "======================================================"
echo ""