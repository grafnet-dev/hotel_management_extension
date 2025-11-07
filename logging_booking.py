
import logging
import os

LOG_DIR = "/opt/odoo-sandbox/log/"   # à adapter, par exemple "/var/log/odoo" /opt/odoo-sandbox/odoo-sandbox.log
LOG_FILE = os.path.join(LOG_DIR, "booking.log")

# Création du répertoire si inexistant
os.makedirs(LOG_DIR, exist_ok=True)

# Récupération d’un logger spécifique
booking_logger = logging.getLogger("hotel.booking")
booking_logger.setLevel(logging.DEBUG)

# Création d’un FileHandler dédié
fh = logging.FileHandler(LOG_FILE)
fh.setLevel(logging.DEBUG)

# Format des logs
formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s')
fh.setFormatter(formatter)

# Éviter d’ajouter plusieurs handlers si déjà configuré
if not booking_logger.handlers:
    booking_logger.addHandler(fh)
