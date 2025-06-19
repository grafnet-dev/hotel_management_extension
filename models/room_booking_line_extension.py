from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta, time

def float_to_time(float_hour):
    hours = int(float_hour)
    minutes = int(round((float_hour - hours) * 60))
    return time(hour=hours, minute=minutes)

class RoomBookingLine(models.Model):
    _inherit = "room.booking.line"
    booking_id = fields.Many2one('room.booking', string="Réservation")
    partner_id = fields.Many2one(related='booking_id.partner_id', string="Client", store=True)

    reservation_type_id = fields.Many2one(
        "hotel.reservation.type",
        string="Type de réservation",
        help="Type de réservation sélectionné pour cette chambre",
    )

    booking_date = fields.Date(
        string="Date de réservation",
        help="Date utilisée pour calculer automatiquement les horaires de check-in et check-out",
    )
    
    booking_end_date = fields.Date(
    string="Date de fin de réservation",
    help="Date de fin utilisée pour calculer la date de départ pour les réservations sur plusieurs nuitées",
    )

    timeline_duration = fields.Integer(
        string="Durée (heures)",
        compute='_compute_timeline_duration',
        help="Durée totale en heures pour l'affichage dans la timeline",
        store=True
    )
    
    timeline_progress = fields.Float(
        string="Progression",
        compute='_compute_timeline_progress',
        help="Pourcentage de temps écoulé pour les réservations en cours",
        store=True
    )
    
    timeline_color = fields.Char(
        compute='_compute_timeline_color',
        string="Couleur Timeline",
        help="Couleur en hexadécimal selon le type de réservation",
        store=True
    )


    # filtrer les types en fonction de la chambre sélectionnée room_id
    @api.onchange("room_id")
    def _onchange_room_id(self):
        if self.room_id:
            return {
                "domain": {
                    "reservation_type_id": [
                        ("id", "in", self.room_id.reservation_type_ids.ids)
                    ]
                }
            }
        else:
            return {"domain": {"reservation_type_id": []}}
    
    # Automatisme principal : remplissage des dates selon le type de reservation
    @api.onchange("reservation_type_id", "booking_date", "booking_end_date", "room_id")
    def _onchange_auto_fill_dates(self):
        self.checkin_date = False
        self.checkout_date = False

        if not self.reservation_type_id or not self.room_id or not self.booking_date:
            return

        if self.reservation_type_id.is_flexible:
            # Ne rien remplir automatiquement
            return 


        # Cherche un slot défini pour cette chambre et ce type
        slot = self.env["hotel.room.reservation.slot"].search(
            [
                ("room_id", "=", self.room_id.id),
                ("reservation_type_id", "=", self.reservation_type_id.id),
            ],
            limit=1,
        )

        if not slot:
            return  

        try:
            
            checkin_time = float_to_time(slot.checkin_time)
            checkout_time = float_to_time(slot.checkout_time)
            # Construit le check-in
            checkin_dt = datetime.combine(self.booking_date, checkin_time)

            if self.reservation_type_id.code == "classic" and self.booking_end_date:
                # Pour plusieurs nuitées, checkout = date de fin à l'heure de fin
                checkout_dt = datetime.combine(self.booking_end_date, checkout_time)
            else:
                # Par défaut, checkout le même jour (day use)
                checkout_dt = datetime.combine(self.booking_date, checkout_time)

                # Pour les nuitées avec checkout avant checkin, on décale d'un jour
                if self.reservation_type_id.code == "classic" and checkout_dt <= checkin_dt:
                    checkout_dt += timedelta(days=1)

            self.checkin_date = checkin_dt
            self.checkout_date = checkout_dt
             # En cas de problème de conversion (rare mais prudent)
        except Exception as e:
            raise ValidationError(_("Erreur lors du calcul des horaires : %s") % str(e))


    # Validation (ex. dates obligatoires sauf si flexible)
    @api.constrains("reservation_type_id", "checkin_date", "checkout_date")
    def _check_dates_required(self):
        for rec in self:
            if rec.reservation_type_id and rec.reservation_type_id.is_flexible:
                if not rec.checkin_date or not rec.checkout_date:
                    raise ValidationError(
                        "Pour une réservation flexible, les dates doivent être saisies manuellement."
                    )

    @api.constrains("booking_date", "booking_end_date", "reservation_type_id")
    def _check_booking_dates_order(self):
        for rec in self:
            if (
                rec.reservation_type_id
                and rec.reservation_type_id.code == "classic"
                and rec.booking_date
                and rec.booking_end_date
                and rec.booking_end_date < rec.booking_date
            ):
                raise ValidationError(
                    _("La date de fin de réservation ne peut pas être antérieure à la date de début.")
                )
            
    
    @api.depends('checkin_date', 'checkout_date')
    def _compute_timeline_duration(self):
        """Compute total duration in hours"""
        for record in self:
            if record.checkin_date and record.checkout_date:
                delta = record.checkout_date - record.checkin_date
                record.timeline_duration = delta.total_seconds() / 3600
            else:
                record.timeline_duration = 0

    @api.depends('checkin_date', 'checkout_date')
    def _compute_timeline_progress(self):
        """Calcule le pourcentage de temps écoulé"""
        now = fields.Datetime.now()
        for record in self:
            if (record.checkin_date and record.checkout_date and 
                record.checkin_date <= now <= record.checkout_date):
                total = (record.checkout_date - record.checkin_date).total_seconds()
                elapsed = (now - record.checkin_date).total_seconds()
                record.timeline_progress = (elapsed / total) * 100
            else:
                record.timeline_progress = 0

    @api.depends('reservation_type_id.code')
    def _compute_timeline_color(self):
        """Définit la couleur selon le type de réservation"""
        color_mapping = {
            'classic': '#4e6ef2', 
            'dayuse': '#67b168',   
            'flexible': '#f2637b'  
        }
        for record in self:
            record.timeline_color = color_mapping.get(record.reservation_type_id.code, '#cccccc')

