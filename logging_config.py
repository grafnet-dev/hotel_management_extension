import logging
import os

LOG_DIR = "/opt/odoo-sandbox/log/"   # à adapter
LOG_FILE = os.path.join(LOG_DIR, "eclc_pricing.log")

# Création du répertoire si inexistant (optionnel)
os.makedirs(LOG_DIR, exist_ok=True)

# Récupération d’un logger spécifique
eclc_logger = logging.getLogger("hotel.eclc")
eclc_logger.setLevel(logging.DEBUG)

# Création d’un FileHandler dédié
fh = logging.FileHandler(LOG_FILE)
fh.setLevel(logging.DEBUG)

# Format des logs
formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s')
fh.setFormatter(formatter)

# Éviter d’ajouter plusieurs handlers si déjà configuré
if not eclc_logger.handlers:
    eclc_logger.addHandler(fh)
