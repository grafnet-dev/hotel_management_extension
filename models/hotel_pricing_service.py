import logging
from datetime import timedelta
from odoo import api, models


class HotelPricingService(models.AbstractModel):
    _name = "hotel.pricing.service"
    _description = "Service central pour le calcul des prix hôteliers"

   # -*- coding: utf-8 -*-

_logger = logging.getLogger(__name__)

class HotelPricingService(models.AbstractModel):
    _name = "hotel.pricing.service"
    _description = "Service central pour le calcul des prix hôteliers"

    @api.model
    def compute_price(self, room_type_id, reservation_type_id, checkin_date, checkout_date, nb_persons=1):
        """
        Calcule le prix total selon unit (night/hour/slot), logue chaque étape.
        Retour: dict {price_total, applied_rule_id, adjustments}
        """
        # Contexte diagnostic
        ctx = {
            "room_type_id": room_type_id,
            "reservation_type_id": reservation_type_id,
            "checkin_date": checkin_date and checkin_date.isoformat(),
            "checkout_date": checkout_date and checkout_date.isoformat(),
            "nb_persons": nb_persons,
        }
        _logger.debug("[PRICING/SVC][IN] %s", ctx)

        adjustments = []
        price_base = 0.0
        applied_rule_id = None

        # 1) Saisons applicables (par check-in)
        season_domain = [
            ("date_start", "<=", checkin_date),
            ("date_end", ">=", checkin_date),
        ]
        seasons = self.env["hotel.season"].search(season_domain, order="priority desc")
        _logger.debug("[PRICING/SVC] Saisons trouvées=%s | domain=%s", seasons.ids, season_domain)

        # 2) Recherche de la règle
        rule_domain = [
            ("room_type_id", "=", room_type_id),
            ("reservation_type_id", "=", reservation_type_id),
            ("active", "=", True),
        ]
        if seasons:
            rule_domain.append(("season_id", "in", seasons.ids))
        else:
            # Fallback: autoriser les règles sans saison (season_id = False)
            rule_domain.append(("season_id", "=", False))

        rule = self.env["hotel.pricing.rule"].search(rule_domain, limit=1)
        _logger.debug("[PRICING/SVC] Rule domain=%s | found=%s", rule_domain, rule.ids)

        if not rule:
            _logger.info("[PRICING/SVC][MISS] Aucune règle tarifaire trouvée | %s", ctx)
            return {"price_total": 0.0, "applied_rule_id": None, "adjustments": []}

        applied_rule_id = rule.id
        _logger.info("[PRICING/SVC] Règle appliquée id=%s | unit=%s | price=%s | currency=%s",
                     rule.id, rule.unit, rule.price, getattr(rule.currency_id, "name", None))

        # 3) Calcul selon l'unité
        if rule.unit == "night":
            delta_days = (checkout_date - checkin_date).days
            nb_nights = max(delta_days, 1)
            price_base = (rule.price or 0.0) * nb_nights
            adjustments.append({"type": "night", "nights": nb_nights, "unit_price": rule.price, "amount": price_base})
            _logger.debug("[PRICING/SVC] NIGHT | delta_days=%s -> nights=%s | unit_price=%s | amount=%s",
                          delta_days, nb_nights, rule.price, price_base)

        elif rule.unit == "hour":
            total_seconds = int((checkout_date - checkin_date).total_seconds())
            nb_hours_raw = total_seconds / 3600.0
            nb_hours = int(nb_hours_raw) or 1  # tronque (6h30 => 6)
            price_base = (rule.price or 0.0) * nb_hours
            adjustments.append({
                "type": "hour", "hours_raw": nb_hours_raw, "hours_billed": nb_hours,
                "unit_price": rule.price, "amount": price_base
            })
            _logger.debug("[PRICING/SVC] HOUR | seconds=%s -> hours_raw=%.4f, billed=%s | unit_price=%s | amount=%s",
                          total_seconds, nb_hours_raw, nb_hours, rule.price, price_base)

        elif rule.unit == "slot":
            price_base = rule.price or 0.0
            adjustments.append({"type": "slot", "unit_price": rule.price, "amount": price_base})
            _logger.debug("[PRICING/SVC] SLOT | forfait | unit_price=%s | amount=%s", rule.price, price_base)

        else:
            _logger.warning("[PRICING/SVC][WARN] Unité inconnue '%s' pour rule=%s", rule.unit, rule.id)

       # 4) Supplément extra-guest (si capacity disponible sur room_type)
        try:
            capacity = getattr(rule.room_type_id, "capacity", None)
            if capacity is not None and nb_persons and nb_persons > capacity:
                extra_count = nb_persons - capacity
                # Tarif configurable par personne supplémentaire (exemple: 10 000 CFA)
                unit_extra = 10000.0  
                extra_amount = extra_count * unit_extra

                adjustments.append({
                    "type": "extra_guest",
                    "capacity": capacity,
                    "persons": nb_persons,
                    "extra_count": extra_count,
                    "unit_extra": unit_extra,
                    "amount": extra_amount,
                })
                _logger.debug(
                    "[PRICING/SVC] EXTRA_GUEST | capacity=%s persons=%s -> extra=%s | +%s",
                    capacity, nb_persons, extra_count, extra_amount,
                )
            else:
                _logger.debug("[PRICING/SVC] EXTRA_GUEST | no extra (capacity=%s, persons=%s)", capacity, nb_persons)
        except Exception:
            _logger.exception("[PRICING/SVC][EXC] Calcul extra_guest")


        # 5) Calcul du total (base + adjustments + supplements - discounts)
        total = price_base
        for adj in adjustments:
            total += adj["amount"]
        #for sup in supplements:
            #total += sup["amount"]
        #for disc in discounts:
            #total -= disc["amount"]

        out = {
            "price_base": float(price_base or 0.0),
            "applied_rule_id": applied_rule_id,
            "adjustments": adjustments,
            #"supplements": supplements,
            #"discounts": discounts,
            "price_total": float(total),
        }
        _logger.info("[PRICING/SVC][OUT] %s", out)
        return out