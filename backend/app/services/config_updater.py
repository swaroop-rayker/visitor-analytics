import logging
from pathlib import Path

logger = logging.getLogger("visitor_analytics.tracker")

def update_env_file(key: str, value: str) -> bool:
    """
    Search for .env configuration files in the app mounts and workspace folders,
    updating the key to the new value in-place or creating it if it does not exist.
    """
    locations = [
        Path("/app/.env"),
        Path(".env"),
        Path("../.env"),
    ]
    
    updated = False
    
    for path in locations:
        try:
            if path.exists() and path.is_file():
                content = path.read_text(encoding="utf-8")
                lines = content.splitlines()
                key_found = False
                new_lines = []
                
                for line in lines:
                    stripped = line.strip()
                    if stripped.startswith(f"{key}=") or stripped.startswith(f"{key} ="):
                        new_lines.append(f"{key}={value}")
                        key_found = True
                    else:
                        new_lines.append(line)
                        
                if not key_found:
                    new_lines.append(f"{key}={value}")
                    
                path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
                updated = True
                logger.info("[CONFIG_UPDATER] Successfully updated key %s in file: %s", key, path)
        except Exception as e:
            logger.error("[CONFIG_UPDATER] Failed to write config change to %s: %s", path, str(e))
            
    return updated
