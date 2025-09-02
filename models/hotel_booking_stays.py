from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError  
from datetime import datetime, timedelta, time
from ..constants.booking_stays_state import STAY_STATES     

def float_to_time(float_hour):
    hours = int(float_hour)
    minutes = int(round((float_hour - hours) * 60))
    return time(hour=hours, minute=minutes)

class HotelBookingStay(models.Model):
    _name = "hotel.booking.stay"
    _description = "Séjour individuel de chaque reservation (booking)"

    # Infos occupants
    occupant_ids = fields.Many2many(
        "res.partner",
        "hotel_booking_stay_res_partner_rel",  
        "stay_id",  
        "partner_id",  
        string="Occupants",
        help="Occupants of the room for this stay",
    )

    occupant_names = fields.Char(
        string="Occupants Names",
        compute="_compute_occupant_names",
        store=True,
        help="List of occupant names, used for display purposes",
    )

    # Identification & Lien
    booking_id = fields.Many2one(
        "room.booking", string="Booking", help="Indicates the Room", ondelete="cascade"
    )
    room_type_id = fields.Many2one(
        "hotel.room.type",
        string="Type de Chambre",
        help="Indicates the Room Type",
        required=True,
    )
    room_id = fields.Many2one(
        "hotel.room",
        string="Chambre",
        help="Indicates the Room",
    )
    reservation_type_id = fields.Many2one(
        "hotel.reservation.type",
        string="Type de réservation",
        help="Type de réservation sélectionné pour cette chambre",
    )
    original_reservation_type_id = fields.Many2one(
        "hotel.reservation.type",
        string="Type d'origine",
        help="Type de réservation sélectionné initialement avant requalification flexible.",
        readonly=True,
        copy=False,
    )
    
    # Dates & Horaires
    booking_start_date = fields.Date(
        string="Date de début de réservation (choisie)",
        help="Date  de début utilisée pour calculer automatiquement les horaires de check-in et check-out",
    )
    booking_end_date = fields.Date(
        string="Date de fin de réservation (choisie)",
        help="Date de fin utilisée pour pour calculer automatiquement les horaires de check-in et check-out",
    )
    
    checkin_date = fields.Datetime(
        string="Check In",
        help="computed based on booking date and room's reservation type slot , or user input for flexible type",
        compute="_compute_checkin_checkout",
        store=True,
    )

    checkout_date = fields.Datetime(
        string="Check Out",
        help="computed based on booking date and room's reservation type slot , or user input for flexible type",
        compute="_compute_checkin_checkout",
        store=True,
    )
    
    is_flexible_reservation = fields.Boolean(
        compute="_compute_is_flexible_reservation", store=False
    )

    # Gestion du early check-in et late check-out
    early_checkin_requested = fields.Boolean("Early Check-in demandé")
    late_checkout_requested = fields.Boolean("Late Check-out demandé")
    early_checkin_hour = fields.Float("Heure Early Check-in", help="Ex: 10.5 = 10h30")
    early_checkin_time_display = fields.Datetime(
        string="Heure Early Check-in (affichée)",
        store=False,
    )

    late_checkout_hour = fields.Float("Heure Late Check-out")
    late_checkout_time_display = fields.Datetime(
        string="Heure Late Check-out (affichée)",
        store=False,
    )
    requalification_reason = fields.Char("Motif de requalification")
    was_requalified_flexible = fields.Boolean("Requalifié en Flexible")
    extra_night_required = fields.Boolean(
        string="Nuit supplémentaire requise", default=False
    )
    is_manual_flexible = fields.Boolean(
        "Flexible sélectionné manuellement",
        help="True si l'utilisateur a directement sélectionné le type flexible, False si requalification automatique",
    )

    # Durée & Unité
    uom_qty = fields.Float(
        string="Duration",
        compute="_compute_duration",
        help="The quantity converted into the UoM used by the product",
        readonly=True,
    )
    uom_id = fields.Many2one(
        "uom.uom",
        string="Unit of Measure",
        help="This will set the unit of measure used",
        readonly=True,
    )

    # consommations du séjour
    need_food = fields.Boolean(
        default=False,
        string="Besoin de nourriture ?",
        help="Check if a Event to be added with the Booking",
    )
    food_order_line_ids = fields.One2many(
        "food.booking.line", "booking_id", string="Food Order Lines", copy=True
    )

    need_service = fields.Boolean(
        default=False,
        string="Besoin de services ?",
        help="Check if a Service to be added with the Stay",
    )
    service_booking_line_ids = fields.One2many(
        "service.booking.line", "booking_id", string="Service Stay Lines", copy=True
    )

    need_fleet = fields.Boolean(
        default=False,
        string="Besoin de véhicule ?",
        help="Check if a Fleet to be added with the Stay",
    )
    fleet_booking_line_ids = fields.One2many(
        "fleet.booking.line",
        "booking_id",
        string="Fleet Stay Lines",
        copy=True,
        help="Check if a Event to be added with the Stay",
    )

    need_event = fields.Boolean(
        default=False,
        string="Participer à un événement ? ",
        help="Check if a Event to be added with the Stay",
    )
    event_booking_line_ids = fields.One2many(
        "event.booking.line", "booking_id", string="Event Stay Lines", copy=True
    )

    # Prix & Facturation
    currency_id = fields.Many2one(
        string="Currency",
        related="booking_id.pricelist_id.currency_id",
        help="The currency used",
    )

    room_price_total = fields.Monetary(
        string="Prix chambre",
        compute="_compute_room_price_total",
        store=True,
        currency_field="currency_id",
    )

    price_subtotal = fields.Float(
        string="Subtotal",
        compute="_compute_price_subtotal",
        help="Total Price excluding Tax",
        store=True,
    )

    price_tax = fields.Float(
        string="Total Tax",
        compute="_compute_price_subtotal",
        help="Tax Amount",
        store=True,
    )
    price_total = fields.Float(
        string="Total",
        compute="_compute_price_subtotal",
        help="Total Price including Tax",
        store=True,
    )

    state = fields.Selection(
        selection=[
            (STAY_STATES["PENDING"], "En attente"),
            (STAY_STATES["ONGOING"], "En cours"),
            (STAY_STATES["COMPLETED"], "Terminé"),
            (STAY_STATES["CANCELLED"], "Annulé"),
        ],
        string="État",
        default=STAY_STATES["PENDING"],
        tracking=True,
    )

    # Méthodes d'action
    def action_start_checkin_wizard(self):
        return {
            "type": "ir.actions.act_window",
            "name": "Fiche de Police",
            "res_model": "hotel.police.form",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_stay_id": self.id,
            },
        }

    def action_start(self):
        self.ensure_one()
        self.state = STAY_STATES["ONGOING"]

    def action_checkout(self):
        self.state = STAY_STATES["COMPLETED"]

    def action_cancel(self):
        self.state = STAY_STATES["CANCELLED"]

    # Computes
    @api.depends("occupant_ids")
    def _compute_occupant_names(self):
        for stay in self:
            stay.occupant_names = (
                ", ".join(stay.occupant_ids.mapped("name")) if stay.occupant_ids else ""
            )

    @api.depends("reservation_type_id")
    def _compute_is_flexible_reservation(self):
        for rec in self:
            rec.is_flexible_reservation = bool(
                rec.reservation_type_id and rec.reservation_type_id.is_flexible
            )

    @api.depends("checkin_date", "checkout_date")
    def _compute_duration(self):
        for rec in self:
            if rec.checkin_date and rec.checkout_date:
                diff = rec.checkout_date - rec.checkin_date
                rec.uom_qty = max(1, diff.days + (1 if diff.total_seconds() > 0 else 0))
                if not rec.uom_id:
                    rec.uom_id = self.env.ref("uom.product_uom_day", raise_if_not_found=False)
            else:
                rec.uom_qty = 0

    @api.depends(
        "booking_start_date", "booking_end_date", "reservation_type_id", "room_type_id"
    )
    def _compute_checkin_checkout(self):
        for rec in self:
            rec.checkin_date = False
            rec.checkout_date = False

            if (
                not rec.booking_start_date
                or not rec.booking_end_date
                or not rec.reservation_type_id
            ):
                continue

            if rec.reservation_type_id.is_flexible:
                continue

            slot = self.env["hotel.room.reservation.slot"].search(
                [
                    ("room_type_id", "=", rec.room_type_id.id),
                    ("reservation_type_id", "=", rec.reservation_type_id.id),
                ],
                limit=1,
            )

            if not slot:
                continue

            rec.checkin_date = datetime.combine(
                rec.booking_start_date, float_to_time(slot.checkin_time)
            )
            rec.checkout_date = datetime.combine(
                rec.booking_end_date, float_to_time(slot.checkout_time)
            )

            if (
                rec.reservation_type_id.code == "classic"
                and rec.checkout_date <= rec.checkin_date
            ):
                rec.checkout_date += timedelta(days=1)

    @api.depends(
        "room_type_id", "reservation_type_id", "booking_start_date", "booking_end_date"
    )
    def _compute_room_price_total(self):
        for stay in self:
            stay.room_price_total = 0.0

            if not (
                stay.room_type_id
                and stay.reservation_type_id
                and stay.booking_start_date
                and stay.booking_end_date
            ):
                continue

            pricing_rule = self.env["hotel.room.pricing"].search(
                [
                    ("room_type_id", "=", stay.room_type_id.id),
                    ("reservation_type_id", "=", stay.reservation_type_id.id),
                    ("active", "=", True),
                ],
                limit=1,
            )

            if not pricing_rule:
                continue

            duration_days = (stay.booking_end_date - stay.booking_start_date).days or 1
            duration_hours = duration_days * 24

            base_price = stay.room_type_id.base_price or 0.0
            stay.room_price_total = pricing_rule.compute_price(
                base_price=base_price, duration_hours=duration_hours
            )

            if pricing_rule.pricing_mode != "hourly":
                stay.room_price_total *= duration_days

    @api.depends(
        "room_price_total",
        "food_order_line_ids.price_subtotal",
        "fleet_booking_line_ids.price_subtotal", 
        "event_booking_line_ids.price_subtotal",
        "service_booking_line_ids.price_subtotal"
    )
    def _compute_price_subtotal(self):
        for stay in self:
            room_total = stay.room_price_total or 0.0
            food_total = sum(line.price_subtotal for line in stay.food_order_line_ids)
            fleet_total = sum(line.price_subtotal for line in stay.fleet_booking_line_ids)
            event_total = sum(line.price_subtotal for line in stay.event_booking_line_ids)
            service_total = sum(line.price_subtotal for line in stay.service_booking_line_ids)
            
            stay.price_subtotal = room_total + food_total + fleet_total + event_total + service_total
            
            tax_rate = 0.18  # À adapter selon tes besoins
            stay.price_tax = stay.price_subtotal * tax_rate
            stay.price_total = stay.price_subtotal + stay.price_tax

    # Onchanges
    @api.onchange("checkin_date", "checkout_date")
    def _onchange_checkin_date(self):
        if (
            self.checkin_date
            and self.checkout_date
            and self.checkout_date < self.checkin_date
        ):
            self.checkout_date = self.checkin_date + timedelta(days=1)
            return {
                "warning": {
                    "title": _("Correction automatique"),
                    "message": _(
                        "La date de départ a été ajustée car elle était avant la date d'arrivée."
                    ),
                }
            }

    @api.onchange(
        "booking_start_date", "booking_end_date", "reservation_type_id", "room_type_id"
    )
    def _onchange_dates_and_type(self):
        for rec in self:
            if (
                not rec.booking_start_date
                or not rec.booking_end_date
                or not rec.reservation_type_id
            ):
                continue

            if rec.reservation_type_id.is_flexible:
                continue

            slot = self.env["hotel.room.reservation.slot"].search(
                [
                    ("room_type_id", "=", rec.room_type_id.id),
                    ("reservation_type_id", "=", rec.reservation_type_id.id),
                ],
                limit=1,
            )

            if not slot:
                continue

            rec.checkin_date = datetime.combine(
                rec.booking_start_date, float_to_time(slot.checkin_time)
            )
            rec.checkout_date = datetime.combine(
                rec.booking_end_date, float_to_time(slot.checkout_time)
            )

            if (
                rec.reservation_type_id.code == "classic"
                and rec.checkout_date <= rec.checkin_date
            ):
                rec.checkout_date += timedelta(days=1)

    # Constraints
    @api.constrains("checkin_date", "checkout_date")
    def _check_dates_required(self):
        for rec in self:
            if (
                rec.checkin_date
                and rec.checkout_date
                and rec.checkout_date < rec.checkin_date
            ):
                raise ValidationError(
                    _("La date de départ ne peut pas être avant la date d'arrivée.")
                )

    @api.constrains("booking_start_date", "booking_end_date", "reservation_type_id")
    def _check_booking_dates_order(self):
        for rec in self:
            if (
                rec.reservation_type_id
                and rec.reservation_type_id.code == "classic"
                and rec.booking_start_date
                and rec.booking_end_date
                and rec.booking_end_date < rec.booking_start_date
            ):
                raise ValidationError(
                    _(
                        "La date de fin de réservation ne peut pas être antérieure à la date de début."
                    )
                )

    # Méthodes API pour UI
    @api.model
    def create_stay_from_ui(self, values):
        if not values.get("room_type_id") or not values.get("booking_id"):
            raise ValidationError(_("Il faut au moins un booking et un type de chambre."))

        stay = self.create(values)

        return {
            "id": stay.id,
            "booking_id": stay.booking_id.id if stay.booking_id else False,
            "room_type": stay.room_type_id.name if stay.room_type_id else None,
            "checkin": stay.checkin_date,
            "checkout": stay.checkout_date,
            "state": stay.state,
        }
        
    @api.model
    def add_stay_to_booking(self, vals):
        try:
            required_fields = ["booking_id", "room_type_id", "reservation_type_id", "booking_start_date", "booking_end_date"]
            for field in required_fields:
                if field not in vals or not vals[field]:
                    raise ValidationError(_("Le champ '%s' est obligatoire.") % field)

            booking = self.env["room.booking"].browse(vals["booking_id"])
            if not booking.exists():
                raise ValidationError(_("La réservation (ID %s) est introuvable.") % vals["booking_id"])

            room_type = self.env["hotel.room.type"].browse(vals["room_type_id"])
            if not room_type.exists():
                raise ValidationError(_("Le type de chambre (ID %s) est introuvable.") % vals["room_type_id"])

            resa_type = self.env["hotel.reservation.type"].browse(vals["reservation_type_id"])
            if not resa_type.exists():
                raise ValidationError(_("Le type de réservation (ID %s) est introuvable.") % vals["reservation_type_id"])

            if vals["booking_end_date"] < vals["booking_start_date"]:
                raise ValidationError(_("La date de fin de réservation ne peut pas être avant la date de début."))

            stay = self.create(vals)

            return {
                "success": True,
                "message": _("Séjour ajouté avec succès à la réservation."),
                "data": {
                    "stay_id": stay.id,
                    "booking_id": booking.id,
                    "state": stay.state,
                    "checkin_date": stay.checkin_date,
                    "checkout_date": stay.checkout_date,
                },
            }

        except (ValidationError, UserError) as e:
            return {
                "success": False,
                "message": str(e),
            }
        except Exception as e:
            return {
                "success": False,
                "message": _("Erreur interne : %s") % str(e),
            }
            
    @api.model
    def compute_checkin_checkout(self, vals):
        try:
            required_fields = ["room_type_id", "reservation_type_id", "booking_start_date", "booking_end_date"]
            for field in required_fields:
                if field not in vals or not vals[field]:
                    raise ValidationError(_("Le champ '%s' est obligatoire.") % field)

            room_type = self.env["hotel.room.type"].browse(vals["room_type_id"])
            if not room_type.exists():
                raise ValidationError(_("Le type de chambre (ID %s) est introuvable.") % vals["room_type_id"])

            resa_type = self.env["hotel.reservation.type"].browse(vals["reservation_type_id"])
            if not resa_type.exists():
                raise ValidationError(_("Le type de réservation (ID %s) est introuvable.") % vals["reservation_type_id"])

            start_date = fields.Date.from_string(vals["booking_start_date"])
            end_date = fields.Date.from_string(vals["booking_end_date"])
            if end_date < start_date:
                raise ValidationError(_("La date de fin de réservation ne peut pas être avant la date de début."))

            rec = self.new({
                "booking_start_date": start_date,
                "booking_end_date": end_date,
                "reservation_type_id": resa_type.id,
                "room_type_id": room_type.id,
            })

            self._compute_checkin_checkout()  # Appel de la méthode compute

            if not rec.checkin_date or not rec.checkout_date:
                return {
                    "success": False,
                    "message": _("Impossible de calculer les dates de séjour (slot manquant ou type flexible)."),
                    "data": {},
                }

            return {
                "success": True,
                "message": _("Dates calculées avec succès."),
                "data": {
                    "checkin_date": rec.checkin_date,
                    "checkout_date": rec.checkout_date,
                },
            }

        except (ValidationError, UserError) as e:
            return {
                "success": False,
                "message": str(e),
                "data": {},
            }
        except Exception as e:
            return {
                "success": False,
                "message": _("Erreur interne : %s") % str(e),
                "data": {},
            }

    # Méthodes de facturation
    def action_auto_create_invoice(self):
        self.ensure_one()
        
        if self.price_total <= 0:
            raise UserError(_("Aucun montant à facturer pour ce séjour."))
        
        partner = False
        if self.booking_id:
            partner = self.booking_id.partner_id
        
        if not partner:
            raise UserError(_("Impossible de créer une facture sans client associé au séjour."))
        
        invoice_vals = {
            'move_type': 'out_invoice',
            'partner_id': partner.id,
            'invoice_date': fields.Date.today(),
            'invoice_origin': f"Séjour {self.id}",
            'narration': f"Facturation séjour du {self.checkin_date} au {self.checkout_date}",
            'currency_id': self.currency_id.id,
        }
        
        invoice = self.env['account.move'].create(invoice_vals)
        
        invoice_lines = []
        
        if self.room_price_total > 0:
            room_product = self._get_or_create_room_product()
            invoice_lines.append((0, 0, {
                'product_id': room_product.id,
                'name': f"Hébergement {self.room_type_id.name} - {self.uom_qty} nuit(s)",
                'quantity': self.uom_qty,
                'price_unit': self.room_price_total / self.uom_qty if self.uom_qty else self.room_price_total,
                'account_id': room_product.property_account_income_id.id,
            }))
        
        for food_line in self.food_order_line_ids:
            if food_line.price_subtotal > 0:
                invoice_lines.append((0, 0, {
                    'product_id': food_line.food_id.id,
                    'name': food_line.food_id.name,
                    'quantity': food_line.uom_qty,
                    'price_unit': food_line.price_unit,
                }))
        
        for fleet_line in self.fleet_booking_line_ids:
            if fleet_line.price_subtotal > 0:
                transport_product = self._get_or_create_transport_product()
                invoice_lines.append((0, 0, {
                    'product_id': transport_product.id,
                    'name': f"Transport - {fleet_line.fleet_id.name if hasattr(fleet_line, 'fleet_id') else 'Véhicule'}",
                    'quantity': fleet_line.uom_qty,
                    'price_unit': fleet_line.price_unit,
                }))
        
        for event_line in self.event_booking_line_ids:
            if event_line.price_subtotal > 0:
                event_product = self._get_or_create_event_product()
                invoice_lines.append((0, 0, {
                    'product_id': event_product.id,
                    'name': f"Événement - {event_line.event_id.name if hasattr(event_line, 'event_id') else 'Activité'}",
                    'quantity': event_line.uom_qty,
                    'price_unit': event_line.price_unit,
                }))
        
        if invoice_lines:
            invoice.write({'invoice_line_ids': invoice_lines})
            invoice._onchange_invoice_line_ids()
        
        if hasattr(self, 'invoice_ids'):
            self.invoice_ids = [(4, invoice.id)]
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'Facture Créée',
            'res_model': 'account.move',
            'res_id': invoice.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def _get_or_create_room_product(self):
        product = self.env['product.product'].search([
            ('name', '=', 'Hébergement Hôtel'),
            ('type', '=', 'service')
        ], limit=1)
        
        if not product:
            product = self.env['product.product'].create({
                'name': 'Hébergement Hôtel',
                'type': 'service',
                'categ_id': self.env.ref('product.product_category_all').id,
                'sale_ok': True,
                'purchase_ok': False,
                'list_price': 100.0,
            })
        
        return product

    def _get_or_create_transport_product(self):
        product = self.env['product.product'].search([
            ('name', '=', 'Service Transport'),
            ('type', '=', 'service')
        ], limit=1)
        
        if not product:
            product = self.env['product.product'].create({
                'name': 'Service Transport',
                'type': 'service',
                'categ_id': self.env.ref('product.product_category_all').id,
                'sale_ok': True,
                'purchase_ok': False,
            })
        
        return product

    def _get_or_create_event_product(self):
        product = self.env['product.product'].search([
            ('name', '=', 'Activité/Événement'),
            ('type', '=', 'service')
        ], limit=1)
        
        if not product:
            product = self.env['product.product'].create({
                'name': 'Activité/Événement',
                'type': 'service',
                'categ_id': self.env.ref('product.product_category_all').id,
                'sale_ok': True,
                'purchase_ok': False,
            })
        
        return product