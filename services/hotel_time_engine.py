# -*- coding: utf-8 -*-
from odoo import models, api, _
from datetime import datetime, timedelta, time

def float_to_time(float_hour):
    hours = int(float_hour)
    minutes = int(round((float_hour - hours) * 60))
    return time(hour=hours, minute=minutes)

class HotelTimeEngine(models.AbstractModel):
    _name = "hotel.time.engine"
    _description = "Hotel Time Engine (Early/Late Evaluation)"

    @api.model
    def evaluate(self, kind, *, requested_hour, room_type_id, base_checkin, base_checkout,
                 early_limit_hour=None, late_limit_hour=None):
        """
        kind: 'early' | 'late'
        requested_hour: float (ex: 10.5)
        room_type_id: id du hotel.room.type (pour contexte/politiques)
        base_checkin / base_checkout: datetimes actuellement calculés
        early_limit_hour / late_limit_hour: (fallback si room_type vide)
        ---
        Retour:
        {
          "accepted": bool,
          "extra_night": bool,
          "pricing_code": "FULL_NIGHT" | "HALF_DAY" | "FREE" | "REJECTED",
          "adjusted_checkin": datetime | None,
          "adjusted_checkout": datetime | None,
          "explanations": str
        }
        """
        RoomType = self.env['hotel.room.type'].browse(room_type_id) if room_type_id else None
        early_limit = RoomType.early_checkin_hour_limit if RoomType and RoomType.exists() else (early_limit_hour or 6.0)
        late_limit  = RoomType.late_checkout_hour_limit if RoomType and RoomType.exists() else (late_limit_hour or 18.0)

        # Sanity
        if not base_checkin or not base_checkout or requested_hour is None:
            return {
                "accepted": False, "extra_night": False, "pricing_code": "REJECTED",
                "adjusted_checkin": None, "adjusted_checkout": None,
                "explanations": _("Inputs incomplets pour l'évaluation horaire.")
            }

        req_t = float_to_time(requested_hour)

        if kind == "early":
            # Early check-in: on ajuste l'arrivée
            requested_dt = datetime.combine(base_checkin.date(), req_t)

            if requested_hour < early_limit:
                # Avant la limite: considéré comme nuit complète en plus
                adjusted = requested_dt - timedelta(days=1)
                return {
                    "accepted": True,
                    "extra_night": True,
                    "pricing_code": "FULL_NIGHT",
                    "adjusted_checkin": adjusted,
                    "adjusted_checkout": base_checkout,  # on ne touche pas le checkout ici
                    "explanations": _("Early avant la limite (%.2f < %.2f) : nuit complète facturée.") % (requested_hour, early_limit),
                }
            else:
                # Dans la fenêtre early partielle
                return {
                    "accepted": True,
                    "extra_night": False,
                    "pricing_code": "HALF_DAY",
                    "adjusted_checkin": requested_dt,
                    "adjusted_checkout": base_checkout,
                    "explanations": _("Early dans la fenêtre autorisée (%.2f ≥ %.2f) : demi-journée / frais partiels.") % (requested_hour, early_limit),
                }

        elif kind == "late":
            # Late check-out: on ajuste le départ
            requested_dt = datetime.combine(base_checkout.date(), req_t)

            if requested_hour > late_limit:
                # Au-delà de la limite: nuit complète en plus
                adjusted = requested_dt + timedelta(days=1) if requested_dt <= base_checkout else requested_dt
                return {
                    "accepted": True,
                    "extra_night": True,
                    "pricing_code": "FULL_NIGHT",
                    "adjusted_checkin": base_checkin,
                    "adjusted_checkout": adjusted,
                    "explanations": _("Late au-delà de la limite (%.2f > %.2f) : nuit complète facturée.") % (requested_hour, late_limit),
                }
            else:
                # Dans la fenêtre late partielle
                return {
                    "accepted": True,
                    "extra_night": False,
                    "pricing_code": "HALF_DAY",
                    "adjusted_checkin": base_checkin,
                    "adjusted_checkout": requested_dt if requested_dt >= base_checkin else base_checkout,
                    "explanations": _("Late dans la fenêtre autorisée (%.2f ≤ %.2f) : demi-journée / frais partiels.") % (requested_hour, late_limit),
                }

        return {
            "accepted": False, "extra_night": False, "pricing_code": "REJECTED",
            "adjusted_checkin": None, "adjusted_checkout": None,
            "explanations": _("Type de demande inconnu: %s") % kind
        }
