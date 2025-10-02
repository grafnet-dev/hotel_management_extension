from odoo import models, api
import random
from ..utils.logger_utils import setup_logger

early_late_logger = setup_logger("hotel.early_late", "early_late.log")


class HotelAvailabilityEngineSim(models.AbstractModel):
    _name = "hotel.availability.engine"
    _description = "Moteur de disponibilité (Simulation)"

    @api.model
    def check_availability(self, room_type_id, start, end):
        """
        Simulation d'un moteur de disponibilité.
        Retourne dispo ou pas avec règles simples/random.
        """
        early_late_logger.info("[AVAIL] Check availability start=%s end=%s room_type=%s",
                               start, end, room_type_id)

        if not room_type_id or not start or not end:
            msg = "⚠️ Données manquantes (room_type_id, start, end)."
            early_late_logger.warning("[AVAIL] %s", msg)
            return {"status": "unavailable", "message": msg}

        duration_hours = (end - start).total_seconds() / 3600.0
        early_late_logger.debug("[AVAIL] Duration=%.2f hours", duration_hours)

        if duration_hours < 24:
            msg = f"✅ Chambre dispo pour {duration_hours:.1f}h."
            early_late_logger.info("[AVAIL] %s", msg)
            return {"status": "available", "message": msg}

        # Random simulation
        choice = random.choice([True, False])
        if choice:
            msg = "✅ Chambre disponible (simulation random)."
            early_late_logger.info("[AVAIL] %s", msg)
            return {"status": "available", "message": msg}
        else:
            msg = "❌ Chambre indisponible (simulation random)."
            early_late_logger.info("[AVAIL] %s", msg)
            return {"status": "unavailable", "message": msg}
