import os
import tarfile
import tempfile
import urllib.request
import urllib.error
import logging
from pathlib import Path
from app.config import settings

logger = logging.getLogger("visitor_analytics.tracker")

GEOIP_UPDATE_IN_PROGRESS = False
LAST_GEOIP_UPDATE_ERROR = None

def download_and_update_geoip() -> bool:
    global GEOIP_UPDATE_IN_PROGRESS, LAST_GEOIP_UPDATE_ERROR
    license_key = getattr(settings, "maxmind_license_key", None)
    if not license_key:
        logger.info("[GEOIP_UPDATE] MAXMIND_LICENSE_KEY is not configured. Skipping auto-update.")
        return False
        
    license_key = license_key.strip()
    GEOIP_UPDATE_IN_PROGRESS = True
    LAST_GEOIP_UPDATE_ERROR = None
    success = True
    try:
        logger.info("[GEOIP_UPDATE] Starting GeoIP database auto-update...")
        
        # Target paths
        city_path = Path(settings.geoip_city_db)
        asn_path = Path(settings.geoip_asn_db)
        
        # Ensure directories exist
        city_path.parent.mkdir(parents=True, exist_ok=True)
        asn_path.parent.mkdir(parents=True, exist_ok=True)
        
        databases = [
            ("GeoLite2-City", city_path),
            ("GeoLite2-ASN", asn_path),
        ]
        
        with tempfile.TemporaryDirectory() as temp_dir:
            for db_name, dest_path in databases:
                url = f"https://download.maxmind.com/app/geoip_download?edition_id={db_name}&license_key={license_key}&suffix=tar.gz"
                tar_path = Path(temp_dir) / f"{db_name}.tar.gz"
                
                try:
                    logger.info(f"[GEOIP_UPDATE] Downloading {db_name} from MaxMind...")
                    req = urllib.request.Request(
                        url,
                        headers={"User-Agent": "Mozilla/5.0"}
                    )
                    with urllib.request.urlopen(req, timeout=60) as response, open(tar_path, "wb") as out_file:
                        out_file.write(response.read())
                    
                    logger.info(f"[GEOIP_UPDATE] Extracting {db_name}...")
                    with tarfile.open(tar_path, "r:gz") as tar:
                        mmdb_member = None
                        for member in tar.getmembers():
                            if member.name.endswith(f"{db_name}.mmdb"):
                                mmdb_member = member
                                break
                        
                        if not mmdb_member:
                            logger.error(f"[GEOIP_UPDATE] {db_name}.mmdb not found in downloaded archive.")
                            success = False
                            continue
                        
                        extracted_file = tar.extractfile(mmdb_member)
                        if extracted_file:
                            temp_dest = dest_path.with_suffix(".tmp")
                            with open(temp_dest, "wb") as f_out:
                                f_out.write(extracted_file.read())
                            
                            temp_dest.replace(dest_path)
                            logger.info(f"[GEOIP_UPDATE] {db_name} database updated successfully.")
                        else:
                            success = False
                except urllib.error.HTTPError as he:
                    logger.warning(f"[GEOIP_UPDATE] HTTP error updating {db_name}: {he.code} - {he.reason}")
                    if he.code == 429:
                        LAST_GEOIP_UPDATE_ERROR = f"MaxMind rate limit exceeded (HTTP 429). Please wait a few hours before retrying."
                    elif he.code in (401, 403):
                        LAST_GEOIP_UPDATE_ERROR = f"Invalid MaxMind license key or permission denied (HTTP {he.code}). Note: new keys can take up to 30 minutes to activate."
                    else:
                        LAST_GEOIP_UPDATE_ERROR = f"MaxMind server error {he.code}: {he.reason}"
                    success = False
                except Exception as e:
                    logger.exception(f"[GEOIP_UPDATE] Failed to update {db_name}: {e}")
                    LAST_GEOIP_UPDATE_ERROR = f"Failed to update {db_name}: {str(e)}"
                    success = False
    finally:
        GEOIP_UPDATE_IN_PROGRESS = False
                
    return success
