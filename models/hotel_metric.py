from odoo import api, fields, models
from datetime import date, timedelta, datetime
import logging

_logger = logging.getLogger(__name__)

class HotelMetric(models.Model):
    _name = "hotel.metric"
    _description = "Daily hotel performance metrics"
    _order = "date desc"

    date = fields.Date(required=True, index=True)
    rooms_total = fields.Integer("Total rooms", readonly=True)
    rooms_occupied = fields.Integer("Rooms occupied", readonly=True)
    rooms_short_stay = fields.Integer("Rooms Short Stays", readonly=True)
    rooms_night_use = fields.Integer("Rooms night use", readonly=True)

    occupancy_rate = fields.Float("Taux d’occupation (%)", readonly=True)
    short_stay_rate = fields.Float("Taux d’utilisation Day Use (%)", readonly=True)
    night_use_rate = fields.Float("Taux d’utilisation Nuitée (%)", readonly=True)

    revenue_total = fields.Float("Revenu total hébergement", readonly=True)
    revpar = fields.Float("RevPAR", readonly=True)

    revenue_short_stay = fields.Float("Revenu Day Use", readonly=True)
    revenue_night_use = fields.Float("Revenu Nuitée", readonly=True)
    revenue_long_stay = fields.Float("Revenu Long Séjour", readonly=True)

    # -----------------------------------------------------
    # 🔹 Fonction utilitaire : répartir le revenu par jour
    # -----------------------------------------------------
    def _split_revenue_by_day(self, stay):
        """Retourne un dictionnaire {date: montant} pour ce séjour."""
        start = stay.planned_checkin_date.date()
        end = stay.planned_checkout_date.date()
        total = stay.total_amount or 0.0

        # Si le séjour commence et finit le même jour → Day Use
        if start == end:
            return {start: total}

        # Si c’est un séjour de plusieurs jours (classique / long stay)
        nights = (end - start).days or 1
        daily = total / nights
        return {start + timedelta(days=i): daily for i in range(nights)}

    # -----------------------------------------------------
    # 🔹 Calcul principal des métriques
    # -----------------------------------------------------
    @api.model
    def _compute_metrics_for_date(self, target_date):
        """Calcule les métriques pour une date donnée à partir des séjours."""
        Room = self.env["hotel.room"]
        Stay = self.env["hotel.booking.stay"]

        rooms_total = Room.search_count([("active", "=", True)])

        start = datetime.combine(target_date, datetime.min.time())
        end = datetime.combine(target_date, datetime.max.time())

        stays = Stay.search([
            ("planned_checkin_date", "<=", end),
            ("planned_checkout_date", ">=", start),
            ("state", "in", ["ongoing"]),
        ])

        # ---- Comptages ----
        rooms_occupied = len(stays.mapped("room_id"))
        short_stays = stays.filtered(lambda s: s.reservation_type_id.code == "flexible")
        night_stays = stays.filtered(lambda s: s.reservation_type_id.code == "classic")

        rooms_short_stay = len(short_stays.mapped("room_id"))
        rooms_night_use = len(night_stays.mapped("room_id"))

        # ---- Calcul des revenus répartis ----
        revenue_total = 0.0
        revenue_short_stay = 0.0
        revenue_night_use = 0.0
        revenue_long_stay = 0.0

        for stay in stays:
            day_revenues = self._split_revenue_by_day(stay)
            amount_today = day_revenues.get(target_date, 0.0)
            revenue_total += amount_today

            # Classification du revenu selon le type
            if stay.planned_checkin_date.date() == stay.planned_checkout_date.date():
                # Day Use
                revenue_short_stay += amount_today
            elif (stay.planned_checkout_date - stay.planned_checkin_date).days == 1:
                # Nuitée classique
                revenue_night_use += amount_today
            else:
                # Long stay (2+ nuits)
                revenue_long_stay += amount_today

            #  Log pour vérification
            _logger.info(f"[METRIC] {stay.name} | {stay.reservation_type_id.code} | "
                         f"Montant total={stay.total_amount} | {target_date} => {amount_today}")

        # ---- Calcul des ratios ----
        occupancy_rate = (rooms_occupied / rooms_total * 100) if rooms_total else 0
        short_stay_rate = (rooms_short_stay / rooms_total * 100) if rooms_total else 0
        night_use_rate = (rooms_night_use / rooms_total * 100) if rooms_total else 0
        revpar = revenue_total / rooms_total if rooms_total else 0

        # ---- Création / mise à jour ----
        vals = {
            "rooms_total": rooms_total,
            "rooms_occupied": rooms_occupied,
            "rooms_short_stay": rooms_short_stay,
            "rooms_night_use": rooms_night_use,
            "occupancy_rate": occupancy_rate,
            "short_stay_rate": short_stay_rate,  # correspond à "flexible"
            "night_use_rate": night_use_rate,
            "revenue_total": revenue_total,
            "revenue_short_stay": revenue_short_stay,
            "revenue_night_use": revenue_night_use,
            "revenue_long_stay": revenue_long_stay,
            "revpar": revpar,
        }

        metric = self.search([("date", "=", target_date)], limit=1)
        if metric:
            metric.write(vals)
        else:
            metric = self.create({**vals, "date": target_date})

        return metric

    # -----------------------------------------------------
    # 🔹 Bouton ou Cron pour le calcul du jour
    # -----------------------------------------------------
    @api.model
    def action_compute_today(self):
        today = fields.Date.today()
        return self._compute_metrics_for_date(today)
