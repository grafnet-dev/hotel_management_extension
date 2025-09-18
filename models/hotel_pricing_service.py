from ..logging_config import eclc_logger as _logger
from datetime import timedelta
from odoo import api, models, fields
from odoo.exceptions import ValidationError, UserError
from ..logging_booking import booking_logger as _logger_booking


class HotelPricingService(models.AbstractModel):
    _name = "hotel.pricing.service"
    _description = "Service central pour le calcul des prix hôteliers"

    @api.model
    def compute_price(
        self,
        room_type_id,
        reservation_type_id,
        planned_checkin_date,
        planned_checkout_date,
        nb_persons=1,
        pricing_mode=None,
        requested_datetime=None,
    ):
        """
        Calcule le prix total du séjour.
        Structure de sortie préparée pour plusieurs couches :
        {
            "base": {...},         # Prix de base → couche 1
            "adjustments": [...],  # Ajustements auto → couche 2 (ex: extra_guest)
            "supplements": [...],  # Suppléments choisis → couche 3  (à venir ex:Late check-out etc )
            "discounts": [...],    # Réductions → couche 4 (à venir Code promo , remise fidélite etc )
            "currency": "XOF",
            "total": 0.0
        }

        compute_price étendu pour accepter :
        - pricing_mode: str | list[str] | dict
        - requested_datetime: datetime | dict(mode->datetime)


        Si pricing_mode est une liste, on itère dessus et on cumule les suppléments.
        """
        # --- SANITIZER : uniformiser requested_datetime ---
        try:
            if isinstance(requested_datetime, dict):
                # ex: {'early_fee': '2025-09-11T09:00:00'}
                key = next(iter(requested_datetime))
                requested_datetime = requested_datetime.get(key)

            if isinstance(requested_datetime, str):
                requested_datetime = fields.Datetime.from_string(requested_datetime)

        except Exception as e:
            _logger.error(
                "[PRICING/SVC] Erreur parsing requested_datetime=%s | %s",
                requested_datetime,
                str(e),
            )
            requested_datetime = False

        # --- CONTEXTE DE DEBUG  LOG IN -> ---
        ctx = {
            "room_type_id": room_type_id,
            "reservation_type_id": reservation_type_id,
            "planned_checkin_date": planned_checkin_date
            and planned_checkin_date.isoformat(),
            "planned_checkout_date": planned_checkout_date
            and planned_checkout_date.isoformat(),
            "nb_persons": nb_persons,
            "pricing_mode": pricing_mode,
            "requested_datetime": requested_datetime and requested_datetime.isoformat(),
        }

        # Normaliser requested_datetime pour le log
        if isinstance(requested_datetime, dict):
            ctx["requested_datetime"] = {
                k: (v.isoformat() if hasattr(v, "isoformat") else v)
                for k, v in requested_datetime.items()
            }
        elif requested_datetime and hasattr(requested_datetime, "isoformat"):
            ctx["requested_datetime"] = requested_datetime.isoformat()
        else:
            ctx["requested_datetime"] = requested_datetime

        _logger.info("🔎 [PRICING] Début du calcul tarifaire")
        _logger.info("➡️  Paramètres reçus: %s", ctx)

        # --- VARIABLES INTERNES  init---
        adjustments = []  # Contiendra les ajustements auto (extra guest, taxes, etc.)
        supplements = []
        price_base = 0.0  # Montant du prix de base (couche 1)
        applied_rule_id = None  # ID de la règle tarifaire appliquée

        # =========================================================
        # 1) SAISONS APPLICABLES
        # =========================================================
        season_domain = [
            ("date_start", "<=", planned_checkin_date),
            ("date_end", ">=", planned_checkin_date),
        ]
        seasons = self.env["hotel.season"].search(season_domain, order="priority desc")
        _logger.info(
            "📅 Saisons trouvées: %s | Domaine: %s", seasons.ids, season_domain
        )

        # =========================================================
        # 2) RÈGLE TARIFAIRE APPLICABLE
        # =========================================================
        rule_domain = [
            ("room_type_id", "=", room_type_id),
            ("reservation_type_id", "=", reservation_type_id),
            ("active", "=", True),
        ]
        if seasons:
            rule_domain.append(("season_id", "in", seasons.ids))
        else:
            rule_domain.append(("season_id", "=", False))

        rule = self.env["hotel.pricing.rule"].search(rule_domain, limit=1)
        _logger.debug("[PRICING/SVC] Rule domain=%s | found=%s", rule_domain, rule.ids)

        if not rule:
            _logger.warning("⚠️ Aucune règle tarifaire trouvée pour: %s", ctx)
            return {
                "base": None,
                "adjustments": [],
                "supplements": [],
                "discounts": [],
                "currency": "XOF",
                "total": 0.0,
            }

        applied_rule_id = rule.id
        _logger.info(
            "📌 Règle appliquée: id=%s | unité=%s | prix=%s | devise=%s",
            rule.id,
            rule.unit,
            rule.price,
            getattr(rule.currency_id, "name", None),
        )

        # =========================================================
        # 3) CALCUL DU PRIX DE BASE    (COUCHE 1)
        # =========================================================
        nb_nights = nb_hours = 1  # Défaut
        applied_unit_price = None

        if rule.unit == "night":
            delta_days = (planned_checkout_date - planned_checkin_date).days
            nb_nights = max(delta_days, 1)
            price_base = (rule.price or 0.0) * nb_nights
            applied_unit_price = rule.price or 0.0
            _logger.debug(
                "[PRICING/SVC] NIGHT | delta_days=%s -> nights=%s | unit_price=%s | amount=%s",
                delta_days,
                nb_nights,
                rule.price,
                price_base,
            )

        elif rule.unit == "hour":
            total_seconds = int(
                (planned_checkout_date - planned_checkin_date).total_seconds()
            )
            nb_hours = int(total_seconds / 3600.0) or 1
            _logger_booking.debug(
                "⏱️ [PRICING/HOUR] stay=%s | total_seconds=%s | nb_hours=%s",
                total_seconds,
                nb_hours,
            )

            if nb_hours < min(rule.line_ids.mapped("min_duration")):
                _logger_booking.error(
                    "❌ [PRICING/HOUR] Durée trop courte (%s h) < min=%s | stay=%s",
                    nb_hours,
                    min(rule.line_ids.mapped("min_duration")),
                )
                raise ValidationError(
                    "La durée minimum est de 2h pour cette réservation."
                )

            # Vérifier les lignes configurées
            line = self.env["hotel.pricing.rule.line"].search(
                [
                    ("rule_id", "=", rule.id),
                    ("min_duration", "<=", nb_hours),
                    "|",
                    ("max_duration", ">=", nb_hours),
                    ("max_duration", "=", False),
                ],
                limit=1,
                order="min_duration asc",
            )

            if line:
                price_base = line.price
                applied_unit_price = line.price or 0.0
                _logger.debug(
                    "[PRICING/SVC] HOUR-FLEX | nb_hours=%s | line=%s | prix=%s",
                    nb_hours,
                    line.id,
                    line.price,
                )

                _logger_booking.info(
                    "✅ [PRICING/HOUR] stay=%s | line_id=%s | min_dur=%s | max_dur=%s | prix=%s",
                    line.id,
                    line.min_duration,
                    line.max_duration,
                    line.price,
                )
            else:
                # Aucune ligne trouvée → déterminer le dernier max configuré (ignorer max_duration=False)
                max_values = [
                    l.max_duration
                    for l in rule.line_ids
                    if l.max_duration not in (False, None)
                ]
                last_max = max(max_values) if max_values else None

                if last_max is not None and nb_hours > last_max:
                    # > last_max => bascule sur tarification nuitée (si présente)
                    night_rule = self.env["hotel.pricing.rule"].search(
                        [
                            ("room_type_id", "=", room_type_id),
                            ("unit", "=", "night"),
                            ("active", "=", True),
                        ],
                        limit=1,
                    )

                    _logger_booking.debug(
                        "🔍 [PRICING/HOUR->NIGHT] Recherche règle nuitée | room_type=%s | res_type=%s | trouvée=%s | ID=%s | prix=%s",
                        room_type_id,
                        reservation_type_id,
                        bool(night_rule),
                        night_rule.id if night_rule else None,
                        night_rule.price if night_rule else None,
                    )

                    if night_rule:
                        delta_days = (
                            planned_checkout_date - planned_checkin_date
                        ).days or 1
                        applied_unit_price = float(night_rule.price or 0.0)
                        price_base = applied_unit_price * delta_days

                        _logger.info(
                            "[PRICING/SVC] HOUR-FLEX > bascule sur NIGHT | %s jrs | unit_price=%s | amount=%s",
                            delta_days,
                            applied_unit_price,
                            price_base,
                        )

                        _logger_booking.warning(
                            "↪️ [PRICING/HOUR->NIGHT] stay=%s | bascule car %s h > last_max=%s | night_rule=%s | %s jrs | prix=%s",
                            ctx.get("stay_id", "new"),
                            nb_hours,
                            last_max,
                            night_rule.id,
                            delta_days,
                            price_base,
                        )
                    else:
                        # Pas de règle night : erreur métier (on peut aussi décider d'un fallback numeric si tu préfères)
                        _logger_booking.error(
                            "🔥 [PRICING/HOUR] Aucune règle 'night' trouvée pour bascule > %s h | ctx=%s",
                            last_max,
                            ctx,
                        )
                        raise ValidationError(
                            f"Aucune règle nuitée trouvée pour bascule après {last_max}h. "
                            "Veuillez configurer une règle 'night' pour permettre la facturation."
                        )

        elif rule.unit == "slot":
            price_base = rule.price or 0.0
            applied_unit_price = rule.price or 0.0
            _logger.debug(
                "[PRICING/SVC] SLOT | forfait | unit_price=%s | amount=%s",
                rule.price,
                price_base,
            )

        else:
            _logger.warning(
                "[PRICING/SVC][WARN] Unité inconnue '%s' pour rule=%s",
                rule.unit,
                rule.id,
            )

        # =========================================================
        # 4) AJUSTEMENTS AUTOMATIQUES   (COUCHE 2)
        # =========================================================
        try:
            capacity = getattr(rule.room_type_id, "capacity", None)
            if capacity and nb_persons and nb_persons > capacity:
                extra_count = nb_persons - capacity
                unit_extra = 0.0  # TODO: paramétrer dans le modèle
                extra_amount = extra_count * unit_extra

                adjustments.append(
                    {
                        "type": "extra_guest",
                        "label": "Supplément personne supplémentaire",
                        "capacity": capacity,
                        "persons": nb_persons,
                        "extra_count": extra_count,
                        "unit_extra": unit_extra,
                        "amount": extra_amount,
                    }
                )
                _logger.debug(
                    "[PRICING/SVC] EXTRA_GUEST | capacity=%s persons=%s -> extra=%s | +%s",
                    capacity,
                    nb_persons,
                    extra_count,
                    extra_amount,
                )
        except Exception:
            _logger.exception("[PRICING/SVC][EXC] Calcul extra_guest")

        # =========================================================
        # 4 bis) SUPPLEMENTS OPTIONNELS (early / late checkout)
        # =========================================================
        supplements = []

        # Normaliser pricing_mode en liste
        modes = []
        if pricing_mode is None:
            modes = []
        elif isinstance(pricing_mode, list):
            modes = pricing_mode
        elif isinstance(pricing_mode, str):
            modes = [pricing_mode]
        elif isinstance(pricing_mode, dict):
            # si on a un dict mode -> datetime, prendre les clés
            modes = list(pricing_mode.keys())
        else:
            # fallback
            try:
                modes = list(pricing_mode)
            except Exception:
                modes = [str(pricing_mode)]

        # Normaliser requested_datetime (on accepte dict ou single datetime)
        requested_map = {}
        if isinstance(requested_datetime, dict):
            requested_map = requested_datetime
        elif requested_datetime and hasattr(requested_datetime, "isoformat"):
            # pas de mapping, appliquer la même dt à tous si nécessaire
            requested_map = {m: requested_datetime for m in modes}

        # itérer sur les modes (dédupliquer pour éviter double charge accidentelle)
        for mode in list(dict.fromkeys(modes)):
            try:
                if mode == "early_fee":
                    amount = getattr(rule.room_type_id, "early_checkin_fee", 15000.0)
                    req_dt = requested_map.get("early_fee")
                    supplements.append(
                        {
                            "type": "early_checkin",
                            "label": "Supplément Early check-in",
                            "amount": float(amount or 0.0),
                            "currency": (
                                rule.currency_id.name if rule.currency_id else "XOF"
                            ),
                            "requested_datetime": (
                                req_dt.isoformat()
                                if hasattr(req_dt, "isoformat")
                                else req_dt
                            ),
                        }
                    )
                    _logger.info(
                        "Ajout du supplément Early check-in (%.2f) pour le mode %s",
                        amount,
                        mode,
                    )

                elif mode == "late_fee":
                    amount = getattr(rule.room_type_id, "late_checkout_fee", 15000.0)
                    req_dt = requested_map.get("late_fee")
                    supplements.append(
                        {
                            "type": "late_checkout",
                            "label": "Supplément Late check-out",
                            "amount": float(amount or 0.0),
                            "currency": (
                                rule.currency_id.name if rule.currency_id else "XOF"
                            ),
                            "requested_datetime": (
                                req_dt.isoformat()
                                if hasattr(req_dt, "isoformat")
                                else req_dt
                            ),
                        }
                    )
                    _logger.info(
                        "Ajout du supplément Late check-out (%.2f) pour le mode %s",
                        amount,
                        mode,
                    )

                elif mode == "extra_night":
                    # On tente d'utiliser le prix unitaire de la règle (comportement plus cohérent)
                    if rule.unit == "night" and rule.price:
                        extra_amount = float(rule.price)
                    else:
                        extra_amount = getattr(
                            rule.room_type_id, "extra_night_amount", 50000.0
                        )

                    supplements.append(
                        {
                            "type": "extra_night",
                            "label": "Nuit supplémentaire",
                            "amount": float(extra_amount),
                            "currency": (
                                rule.currency_id.name if rule.currency_id else "XOF"
                            ),
                        }
                    )
                    _logger.info(
                        "Ajout du supplément Nuit supplémentaire (%.2f) pour le mode %s",
                        extra_amount,
                        mode,
                    )

                else:
                    _logger.warning(
                        "Mode de tarification inconnu : %s (aucun supplément ajouté)",
                        mode,
                    )

            except Exception as e:
                _logger.error(
                    "Erreur lors de l'ajout du supplément pour le mode %s : %s",
                    mode,
                    str(e),
                )
        # =========================================================
        # 5) CALCUL FINAL DU TOTAL
        # =========================================================
        # total = price_base
        # for adj in adjustments:
        #   if adj["type"] != "night" and adj["type"] != "hour" and adj["type"] != "slot":
        #      total += adj["amount"]

        # for sup in supplements:
        #     total += sup.get("amount", 0.0)

        total = price_base
        for adj in adjustments:
            total += adj.get("amount", 0.0)

        for sup in supplements:
            total += sup.get("amount", 0.0)

        _logger.info(
            "💰 Total calculé: base=%s + adj=%s + sup=%s = %s",
            price_base,
            sum(a.get("amount", 0.0) for a in adjustments),
            sum(s.get("amount", 0.0) for s in supplements),
            total,
        )

        # =========================================================
        # 6) STRUCTURE DE SORTIE FINALE
        # =========================================================
        out = {
            "base": {
                "rule_id": applied_rule_id,
                "unit": rule.unit,
                "unit_price": applied_unit_price,
                "quantity": (
                    nb_nights
                    if rule.unit == "night"
                    else nb_hours if rule.unit == "hour" else 1
                ),
                "amount": price_base,
            },
            "adjustments": adjustments,  #
            "supplements": supplements,  #
            "discounts": [],  #
            "currency": rule.currency_id.name if rule.currency_id else "XOF",
            "total": float(total),
        }

        _logger.info("[PRICING/SVC][OUT] %s", out)
        return out
