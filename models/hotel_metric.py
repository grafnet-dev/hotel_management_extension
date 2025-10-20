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
    
    # === MÉTRIQUES RESTAURATION ===
    pos_orders_count = fields.Integer("Nombre de ventes POS", readonly=True)
    pos_revenue_total = fields.Float("Revenu total restauration", readonly=True)
    pos_top_products = fields.Text("Top plats vendus (classement)", readonly=True)
    pos_inventory_value = fields.Float("Valeur stock restaurant", readonly=True)
    pos_stock_low_count = fields.Integer("Produits faibles en stock", readonly=True)

   
    #  Fonction utilitaire : répartir le revenu par jour
 
    def _split_revenue_by_day(self, stay):
        """Retourne un dictionnaire {date: montant} pour ce séjour."""
        start = stay.planned_checkin_date.date()
        end = stay.planned_checkout_date.date()
        total = stay.room_price_total or 0.0

        # Si le séjour commence et finit le même jour → Day Use
        if start == end:
            return {start: total}

        # Si c’est un séjour de plusieurs jours (classique / long stay)
        nights = (end - start).days or 1
        daily = total / nights
        return {start + timedelta(days=i): daily for i in range(nights)}

    #  Calcul principal des métriques
 
    @api.model
    def _compute_metrics_for_date(self, target_date):
        """Calcule les métriques pour une date donnée à partir des séjours."""
        
        _logger.info(f"🧮 [METRIC] Calcul des métriques pour la date : {target_date}")
        Room = self.env["hotel.room"]
        Stay = self.env["hotel.booking.stay"]

        rooms_total = Room.search_count([("active", "=", True)])
        
        _logger.info(f"➡️ Nombre total de chambres actives : {rooms_total}")

        start = datetime.combine(target_date, datetime.min.time())
        end = datetime.combine(target_date, datetime.max.time())

        stays = Stay.search([
            ("planned_checkin_date", "<=", end),
            ("planned_checkout_date", ">=", start),
            #("state", "in", ["ongoing"]),
        ])
        
        _logger.info(f"➡️ Séjours trouvés ({len(stays)}): {[s.id for s in stays]}")


        # ---- Comptages ----
        rooms_occupied = len(stays.mapped("room_id"))
        short_stays = stays.filtered(lambda s: s.reservation_type_id.code == "flexible")
        night_stays = stays.filtered(lambda s: s.reservation_type_id.code == "classic")

        rooms_short_stay = len(short_stays.mapped("room_id"))
        rooms_night_use = len(night_stays.mapped("room_id"))
        
        _logger.info(f"➡️ Chambres occupées : {rooms_occupied}")
        _logger.info(f"➡️ Séjours Day Use : {len(short_stays)}")
        _logger.info(f"➡️ Séjours Nuitée : {len(night_stays)}")


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
            _logger.info(f"[METRIC] {stay.id} | {stay.reservation_type_id.code} | "
                         f"Montant total={stay.room_price_total} | {target_date} => {amount_today}")
            
            _logger.info(f"   🏨 {stay.id} | type={stay.reservation_type_id.code} | total={stay.room_price_total} | "
                     f"reparti sur {len(day_revenues)} jours | montant du jour={amount_today}")

        # ---- Calcul des ratios ----
        occupancy_rate = (rooms_occupied / rooms_total * 100) if rooms_total else 0
        short_stay_rate = (rooms_short_stay / rooms_total * 100) if rooms_total else 0
        night_use_rate = (rooms_night_use / rooms_total * 100) if rooms_total else 0
        revpar = revenue_total / rooms_total if rooms_total else 0

        _logger.info(f"💰 Revenu total du jour : {revenue_total}")
        _logger.info(f"📊 Taux occupation={occupancy_rate:.2f}%, RevPAR={revpar:.2f}")
        
      
        #  MÉTRIQUES RESTAURATION (POS)
        
        PosOrder = self.env["pos.order"]
        PosLine = self.env["pos.order.line"]
        StockQuant = self.env["stock.quant"]

        # Récupération des commandes POS du jour
        pos_orders = PosOrder.search([
            ("date_order", ">=", start),
            ("date_order", "<=", end),
            ("state", "in", ["paid", "done", "invoiced"]),
        ])

        pos_orders_count = len(pos_orders)
        pos_revenue_total = sum(pos_orders.mapped("amount_total"))

        _logger.info("🍽️ [POS] Commandes trouvées : %s", pos_orders_count)
        for order in pos_orders:
            _logger.info("   🧾 POS Order %s | Total=%.2f | État=%s | Date=%s",
                         order.name, order.amount_total, order.state, order.date_order)

        _logger.info("💰 [POS] Revenu total du jour : %.2f", pos_revenue_total)

        # Lignes POS pour classement des produits
        pos_lines = PosLine.search([("order_id", "in", pos_orders.ids)])
        _logger.info("🍔 [POS] Lignes totales : %s", len(pos_lines))

        product_sales = {}
        for line in pos_lines:
            name = line.product_id.display_name
            qty = line.qty
            product_sales[name] = product_sales.get(name, 0) + qty
            _logger.debug("   ➕ %s vendu %s fois", name, qty)

        top_products = sorted(product_sales.items(), key=lambda x: x[1], reverse=True)
        top_products_str = "\n".join([f"{name}: {qty}" for name, qty in top_products[:5]])

        _logger.info("🏆 [POS] Top produits du jour :\n%s", top_products_str)


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
            "pos_orders_count": pos_orders_count,
            "pos_revenue_total": pos_revenue_total,
            "pos_top_products": top_products_str,
            
        }

        metric = self.search([("date", "=", target_date)], limit=1)
        if metric:
            metric.write(vals)
            _logger.info(f"✅ Mise à jour de la métrique existante ({metric.id}) pour {target_date}")
        else:
            metric = self.create({**vals, "date": target_date})
            _logger.info(f"🆕 Création nouvelle métrique ({metric.id}) pour {target_date}")
        return metric

 
    #  Bouton ou Cron pour le calcul du jour
   
    def action_compute_today(self):
        today = fields.Date.today()
        _logger.info(f"🟦 Bouton Recalcul lancé pour {today}")
        return self._compute_metrics_for_date(today)

    
    # Calcul des métriques sur plusieurs jours

    def action_compute_last_days(self):
        """Calcule les métriques pour les 30 derniers jours."""
        days = 30
        today = fields.Date.today()
        start_date = today - timedelta(days=days - 1)

        for i in range(days):
            target_date = start_date + timedelta(days=i)
            self._compute_metrics_for_date(target_date)
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": " Calcul terminé",
                "message": f"Métriques générées pour les {days} derniers jours.",
                "sticky": False,
            },
        }