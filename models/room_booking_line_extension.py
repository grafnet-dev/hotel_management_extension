from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta, time, date

def float_to_time(float_hour):
    hours = int(float_hour)
    minutes = int(round((float_hour - hours) * 60))
    return time(hour=hours, minute=minutes)

class RoomBookingLine(models.Model):
    _inherit = "room.booking.line"

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

    # Champs pour affichage des heures calculées (formatés en string pour éviter les conversions timezone)
    checkin_time_display = fields.Char(
        string="Check-in calculé",
        compute="_compute_time_display",
        help="Heure de check-in calculée"
    )
    
    checkout_time_display = fields.Char(
        string="Check-out calculé", 
        compute="_compute_time_display",
        help="Heure de check-out calculée"
    )

    @api.depends('checkin_date', 'checkout_date')
    def _compute_time_display(self):
        """Calcule l'affichage des heures sans conversion de timezone"""
        for rec in self:
            if rec.checkin_date:
                # Formatage direct de la date/heure stockée
                rec.checkin_time_display = rec.checkin_date.strftime('%d/%m/%Y %H:%M')
            else:
                rec.checkin_time_display = ''
                
            if rec.checkout_date:
                rec.checkout_time_display = rec.checkout_date.strftime('%d/%m/%Y %H:%M')
            else:
                rec.checkout_time_display = ''

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
    
    # Gestion automatique des dates pour day-use - MODIFIÉ
    @api.onchange("booking_date", "reservation_type_id")
    def _onchange_booking_date_dayuse(self):
        if self.reservation_type_id and self.reservation_type_id.code == "day_use":
            # Pour day-use, on vide la date de fin au lieu de l'égaler à la date de début
            self.booking_end_date = False
        elif self.reservation_type_id and self.reservation_type_id.code == "classic" and self.booking_date:
            # Pour les réservations classiques, si pas de date de fin définie, on met la date de début par défaut
            if not self.booking_end_date:
                self.booking_end_date = self.booking_date
    
    # Automatisme principal : remplissage des dates selon le type de reservation
    @api.onchange("reservation_type_id", "booking_date", "booking_end_date", "room_id")
    def _onchange_auto_fill_dates(self):
        self.checkin_date = False
        self.checkout_date = False

        if not self.reservation_type_id or not self.room_id or not self.booking_date:
            return

        if self.reservation_type_id.is_flexible:
            # Ne rien remplir automatiquement
            return # Pas de calcul auto pour les flexibles

        # Cherche un slot défini pour cette chambre et ce type
        slot = self.env["hotel.room.reservation.slot"].search(
            [
                ("room_id", "=", self.room_id.id),
                ("reservation_type_id", "=", self.reservation_type_id.id),
            ],
            limit=1,
        )

        if not slot:
            return  # Aucun slot trouvé → pas de remplissage automatique

        try:
            checkin_time = float_to_time(slot.checkin_time)
            checkout_time = float_to_time(slot.checkout_time)
            
            # Création des datetime "naive" (sans timezone) pour correspondre exactement aux heures configurées
            checkin_dt = datetime.combine(self.booking_date, checkin_time) + timedelta(minutes=15)

            if self.reservation_type_id.code == "classic":
                end_date = self.booking_end_date or self.booking_date
            else:
                end_date = self.booking_date  # pour day-use ou autre

            if not end_date:
                raise ValidationError(_("Impossible de calculer la date de départ sans date de fin ou date de début."))

            checkout_dt = datetime.combine(end_date, checkout_time) + timedelta(minutes=15)

                # Pour les nuitées avec checkout avant checkin, on décale d'un jour
            if self.reservation_type_id.code == "classic" and checkout_dt <= checkin_dt:
                checkout_dt += timedelta(days=1)
                
            # Stockage des datetime "naive" pour éviter les conversions automatiques 
            self.checkin_date = checkin_dt
            self.checkout_date = checkout_dt
            
        except Exception as e:
            raise ValidationError(_("Erreur lors du calcul des horaires : %s") % str(e))

    # Méthode onchange pour vérifier les conflits de réservation
    @api.onchange('checkin_date')
    def onchange_checkin_date(self):
        """Check for overlapping reservations when checkin_date changes"""
        if not self.checkin_date or not self.checkout_date or not self.room_id:
            return
        
        # Convert to datetime if needed
        if isinstance(self.checkin_date, date) and not isinstance(self.checkin_date, datetime):
            rec_checkin_date = datetime.combine(self.checkin_date, time.min)
        else:
            rec_checkin_date = self.checkin_date
            
        if isinstance(self.checkout_date, date) and not isinstance(self.checkout_date, datetime):
            rec_checkout_date = datetime.combine(self.checkout_date, time.min)
        else:
            rec_checkout_date = self.checkout_date
        
        # Search for overlapping reservations
        overlapping_lines = self.env['room.booking.line'].search([
            ('room_id', '=', self.room_id.id),
            ('id', '!=', self.id),  # Exclude current record
            ('checkin_date', '!=', False),  # Ensure dates are set
            ('checkout_date', '!=', False),
        ])
        
        for line in overlapping_lines:
            # Skip if the other line doesn't have valid dates
            if not line.checkin_date or not line.checkout_date:
                continue
                
            # Convert line dates to datetime if needed
            if isinstance(line.checkin_date, date) and not isinstance(line.checkin_date, datetime):
                line_checkin = datetime.combine(line.checkin_date, time.min)
            else:
                line_checkin = line.checkin_date
                
            if isinstance(line.checkout_date, date) and not isinstance(line.checkout_date, datetime):
                line_checkout = datetime.combine(line.checkout_date, time.min)
            else:
                line_checkout = line.checkout_date
            
            # Check for overlap
            if (rec_checkin_date <= line_checkin <= rec_checkout_date or
                rec_checkin_date <= line_checkout <= rec_checkout_date or
                line_checkin <= rec_checkin_date <= line_checkout):
                
                return {
                    'warning': {
                        'title': _('Conflit de réservation'),
                        'message': _('Cette chambre est déjà réservée pour cette période. '
                                   'Veuillez choisir une autre date ou une autre chambre.')
                    }
                }

    # Validation des dates (nouvelles contraintes)
    @api.constrains("booking_date")
    def _check_booking_date_not_past(self):
        for rec in self:
            if rec.booking_date and rec.booking_date < date.today():
                raise ValidationError(
                    _("La date de réservation ne peut pas être antérieure à aujourd'hui.")
                )

    @api.constrains("booking_date", "booking_end_date")
    def _check_booking_dates_order(self):
        for rec in self:
            if (rec.booking_date and rec.booking_end_date and 
                rec.booking_end_date < rec.booking_date):
                raise ValidationError(
                    _("La date de fin ne peut pas être antérieure à la date de début.")
                )

    # Validation spécifique pour day-use - MODIFIÉE
    @api.constrains("reservation_type_id", "booking_end_date")
    def _check_dayuse_no_end_date(self):
        for rec in self:
            if (rec.reservation_type_id and 
                rec.reservation_type_id.code == "day_use" and
                rec.booking_end_date):
                raise ValidationError(
                    _("Pour une réservation day-use, la date de fin ne doit pas être renseignée.")
                )

    # Validation (ex. dates obligatoires sauf si flexible)
    @api.constrains("reservation_type_id", "checkin_date", "checkout_date")
    def _check_dates_required(self):
        for rec in self:
            if rec.reservation_type_id and rec.reservation_type_id.is_flexible:
                if not rec.checkin_date or not rec.checkout_date:
                    raise ValidationError(
                        "Pour une réservation flexible, les dates doivent être saisies manuellement."
                    )

    # Ancienne validation reformulée pour éviter les doublons
    @api.constrains("booking_date", "booking_end_date", "reservation_type_id")
    def _check_classic_booking_dates(self):
        for rec in self:
            if (rec.reservation_type_id and 
                rec.reservation_type_id.code == "classic" and
                rec.booking_date and rec.booking_end_date and
                rec.booking_end_date < rec.booking_date):
                raise ValidationError(
                    _("Pour une réservation classique, la date de fin ne peut pas être antérieure à la date de début.")
                )