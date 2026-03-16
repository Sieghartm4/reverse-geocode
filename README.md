# 🌏 OSM Philippines Reverse Geocoding API

A high-performance Flask API for reverse geocoding using OpenStreetMap Philippines data stored in PostgreSQL with PostGIS. This API extracts detailed address components including house numbers, road names, neighbourhoods, and postcodes.

## 🚀 Features

- **Fast spatial queries** using PostGIS indexes
- **Detailed address extraction** from OSM hstore tags
- **Philippine-specific parsing** for block/lot/unit numbers
- **Optimized for Philippines OSM data**
- **Debug endpoint** for data inspection
- **Production-ready** with connection pooling

## 📋 Requirements

- Ubuntu 18.04+ / Linux
- PostgreSQL 12+ with PostGIS
- Python 3.7+
- OSM Philippines data

## 🛠️ Installation

### 1. System Dependencies

```bash
sudo apt update
sudo apt upgrade -y
sudo apt install -y postgresql postgresql-contrib postgis osm2pgsql python3-pip python3-venv
```

### 2. Database Setup

```bash
# Switch to postgres user
sudo -u postgres psql

# Create database
CREATE DATABASE ph_geodata;

# Enable PostGIS
\c ph_geodata
CREATE EXTENSION postgis;
\q
```

### 3. Download Philippines OSM Data

```bash
mkdir ~/osm
cd ~/osm
wget https://download.geofabrik.de/asia/philippines-latest.osm.pbf
```

### 4. Import OSM Data

```bash
# Note: The downloaded file will have a date-based name like philippines-260315.osm.pbf
# Use the actual filename you downloaded
ls *.osm.pbf

osm2pgsql \
-d ph_geodata \
-U postgres \
--create \
--slim \
-G \
--hstore \
--number-processes 4 \
philippines-*.osm.pbf
```

### 5. Python Environment

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
pip install flask psycopg2-binary psycopg2-extras
```

## 🐍 Python Libraries Used

```python
flask==2.3.3          # Web framework
psycopg2-binary==2.9.7 # PostgreSQL adapter
psycopg2-extras==2.9.7 # Additional PostgreSQL tools (RealDictCursor)
re                   # Regular expressions (built-in)
time                 # Performance timing (built-in)
```

Install with:
```bash
pip install flask psycopg2-binary psycopg2-extras
```

## ⚙️ Configuration

### Database Connection

Edit the database connection in `reverse-geo-api.py`:

```python
def _new_conn():
    c = psycopg2.connect(
        "dbname=ph_geodata user=postgres password=yourpassword",
        application_name="reverse_geocoder"
    )
    c.autocommit = True
    return c
```

### Update Password

Replace `yourpassword` with your actual PostgreSQL password.

## 🚀 Running the API

### Development Mode

```bash
python reverse-geo-api.py
```

### Production Mode

```bash
pip install gunicorn
gunicorn -w 4 reverse-geo-api:app -b 0.0.0.0:5111
```

## 📡 API Endpoints

### Reverse Geocoding

**GET** `/reverse?lat={latitude}&lon={longitude}`

Example:
```bash
curl "http://localhost:5111/reverse?lat=14.3258395&lon=121.0136624"
```

Response:
```json
{
  "data": {
    "display_name": "3224 Linden Street, Saint Joseph Village 10, Langgam, San Pedro, Laguna, 4023, Philippines",
    "elapsed_ms": 45.2,
    "address": {
      "unit": "",
      "block": "",
      "lot": "",
      "house_number": "3224",
      "building": "",
      "road": "Linden Street",
      "neighbourhood": "Saint Joseph Village 10",
      "suburb": "Langgam",
      "district": "",
      "city": "San Pedro",
      "county": "",
      "state": "Laguna",
      "region": "",
      "postcode": "4023",
      "country": "Philippines",
      "country_code": "ph"
    }
  }
}
```

### Debug Endpoint

**GET** `/debug?lat={latitude}&lon={longitude}`

Shows raw OSM data for debugging:
```bash
curl "http://localhost:5111/debug?lat=14.3258395&lon=121.0136624"
```

## 🔧 Performance Optimization

### Spatial Indexes

The API automatically creates these indexes on startup:

```sql
CREATE INDEX idx_osm_line_way ON planet_osm_line USING GIST(way);
CREATE INDEX idx_osm_point_way ON planet_osm_point USING GIST(way);
CREATE INDEX idx_osm_polygon_way ON planet_osm_polygon USING GIST(way);
```

### Query Optimization

- Uses EPSG:3857 for spatial calculations (native projection)
- Bounding-box pre-filtering with `ST_Expand`
- Single round-trip database queries
- Connection pooling with auto-reconnect

## 🏗️ Architecture

### Database Tables

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `planet_osm_point` | Address nodes, POIs | `tags` (hstore), `way` |
| `planet_osm_line` | Roads, paths | `highway`, `name`, `way` |
| `planet_osm_polygon` | Buildings, boundaries | `building`, `admin_level`, `way` |

### Address Extraction Logic

1. **Road Detection**: Nearest named road with highway priority
2. **Admin Boundaries**: Hierarchical (barangay → city → province → region)
3. **Address Nodes**: Extract house numbers, street names, postcodes
4. **Buildings**: Block/lot/unit parsing for Philippine addresses
5. **Neighbourhoods**: Subdivision/village/phase detection

## 🇵🇭 Philippine Address Features

### Block/Lot/Unit Parser

```python
# Parses addresses like:
# "Blk 21 Lot 28" → block="21", lot="28"
# "Unit 3B" → unit="3B"
# "3224" → house_number="3224"
```

### Subdivision Detection

Recognizes common Philippine subdivision keywords:
- village, subdivision, phase, estate, compound
- homes, residences, heights, springs, gardens

## 🔍 Testing

### Test Coordinates

```bash
# San Pedro, Laguna (complex address)
curl "http://localhost:5111/reverse?lat=14.3258395&lon=121.0136624"

# Manila (urban area)
curl "http://localhost:5111/reverse?lat=14.599512&lon=120.984219"

# Rural area
curl "http://localhost:5111/reverse?lat=15.480000&lon=120.950000"
```

### Performance Testing

```bash
# Time the API
time curl "http://localhost:5111/reverse?lat=14.3258395&lon=121.0136624"
```

Expected: < 100ms response time

## 🚀 Deployment

### Systemd Service

Create `/etc/systemd/system/reverse-geocode.service`:

```ini
[Unit]
Description=Reverse Geocoding API
After=network.target postgresql.service

[Service]
Type=exec
User=ubuntu
Group=ubuntu
WorkingDirectory=/home/ubuntu/reverse-geocode-api
Environment=PATH=/home/ubuntu/reverse-geocode-api/venv/bin
ExecStart=/home/ubuntu/reverse-geocode-api/venv/bin/gunicorn -w 4 reverse-geo-api:app -b 0.0.0.0:5111
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable reverse-geocode
sudo systemctl start reverse-geocode
```

### Nginx Reverse Proxy

Create `/etc/nginx/sites-available/reverse-geocode`:

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:5111;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

Enable:
```bash
sudo ln -s /etc/nginx/sites-available/reverse-geocode /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

## 📊 Storage Requirements

| Component | Size |
|-----------|------|
| OSM PBF file | ~250MB |
| PostgreSQL database | ~2-4GB |
| Indexes | ~1-2GB |
| **Total** | **~5GB** |

## 🔧 Troubleshooting

### Common Issues

1. **Connection refused**: Check PostgreSQL is running
2. **Slow queries**: Verify spatial indexes exist
3. **Missing data**: Ensure OSM import completed successfully
4. **Permission denied**: Check database user permissions

### Debug Commands

```bash
# Check PostgreSQL status
sudo systemctl status postgresql

# Verify database
sudo -u postgres psql -d ph_geodata -c "\dt"

# Test spatial query
sudo -u postgres psql -d ph_geodata -c "
SELECT COUNT(*) FROM planet_osm_point WHERE name IS NOT NULL LIMIT 1;
"
```

## 📝 License

This project is open-source. Please comply with OpenStreetMap data licensing requirements when deploying commercially.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📞 Support

For issues and questions:
- Check the debug endpoint for data inspection
- Review PostgreSQL logs
- Verify OSM data quality for your target area

---

**🚀 Ready to deploy your Philippine reverse geocoding service!**
