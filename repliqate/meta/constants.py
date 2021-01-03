import pkgutil

# Application version stamp.
try:
    REPLIQATE_VERSION = pkgutil.get_data('repliqate.meta', 'VERSION').decode('UTF-8', 'ignore')
except Exception:
    REPLIQATE_VERSION = 'unknown'
