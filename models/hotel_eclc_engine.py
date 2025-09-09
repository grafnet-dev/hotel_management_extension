from ..logging_config import eclc_logger as _logger
from odoo import models, api
from datetime import datetime


class HotelECLCEngine(models.AbstractModel):
    _name = "hotel.eclc.engine"
    _description = "Moteur Early Check-in / Late Check-out"

    @api.model
    def evaluate_request(self, request_type, requested_datetime, planned_datetime, room_type_id):
        """
        Vérifie si l'early check-in ou late check-out est autorisé
        ou si une nuit supplémentaire doit être ajoutée.

        :param request_type: "early" ou "late"
        :param requested_datetime: Datetime demandé par le client
        :param planned_datetime: Datetime prévu standard
        :param room_type_id: ID du type de chambre concerné
        :return: dict avec résultat + pricing_mode
        """
        
        _logger.info("🔎 [ECLC] Évaluation de la demande")
        _logger.info(
            "➡️  Type: %s | Demande: %s | Prévu: %s | RoomType ID: %s",
            request_type,
            requested_datetime,
            planned_datetime,
            room_type_id,
        )

        room_type = self.env["hotel.room.type"].browse(room_type_id)
        result = {
            "request_type": request_type,
            "requested_datetime": requested_datetime,
            "planned_datetime": planned_datetime,
            "difference_hours": 0.0,   # 
            "status": "accepted",      #
            "pricing_mode": None,      # 
            "message": "",
        }

        if not requested_datetime or not planned_datetime:
            _logger.warning("⚠️ Données horaires manquantes (requested=%s, planned=%s)", requested_datetime, planned_datetime)
            result.update({
                "status": "refused",
                "message": "Données horaires incomplètes.",
                "pricing_mode": "invalid_request"
            })
            return result

        # Calcul de la différence en heures (pour reporting)
        diff = (planned_datetime - requested_datetime).total_seconds() / 3600.0 \
               if request_type == "early" \
               else (requested_datetime - planned_datetime).total_seconds() / 3600.0
        result["difference_hours"] = round(diff, 2)
        _logger.info("🕒 Différence calculée: %.2f heures", result["difference_hours"])

        requested_hour = requested_datetime.hour + requested_datetime.minute / 60.0
        _logger.info("🕑 Heure demandée: %.2f h", requested_hour)


        if request_type == "early":
            if requested_hour < room_type.early_checkin_hour_limit:
                result.update({
                    "status": "extra_night",
                    "pricing_mode": "extra_night",
                    "message": f"Arrivée à {requested_hour:.2f}h → nuit supplémentaire requise."
                })
                _logger.info("🏨 Early check-in → Nuit supplémentaire requise (limite=%s)", room_type.early_checkin_hour_limit)
            else:
                result.update({
                    "status": "accepted",
                    "pricing_mode": "early_fee",
                    "message": f"Early check-in accepté ({requested_hour:.2f}h)."
                })
                _logger.info("✅ Early check-in accepté (limite=%s)", room_type.early_checkin_hour_limit)

        elif request_type == "late":
            if requested_hour > room_type.late_checkout_hour_limit:
                result.update({
                    "status": "extra_night",
                    "pricing_mode": "extra_night",
                    "message": f"Départ à {requested_hour:.2f}h → nuit supplémentaire requise."
                })
                _logger.info("🏨 Late check-out → Nuit supplémentaire requise (limite=%s)", room_type.late_checkout_hour_limit)
            else:
                result.update({
                    "status": "accepted",
                    "pricing_mode": "late_fee",
                    "message": f"Late check-out accepté ({requested_hour:.2f}h)."
                })
                _logger.info("✅ Late check-out accepté (limite=%s)", room_type.late_checkout_hour_limit)

        else:
            result.update({
                "status": "refused",
                "pricing_mode": "invalid_request",
                "message": "Type de demande invalide (doit être 'early' ou 'late')."
            })
            _logger.error("❌ Type de demande invalide reçu: %s", request_type)

        _logger.info("📦 Résultat final: %s", result)
        return result
