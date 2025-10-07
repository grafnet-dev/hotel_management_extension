from odoo import models, fields, api
from datetime import date


class HotelPoliceForm(models.Model):
    _name = "hotel.police.form"
    _description = "Fiche de police pour client"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    # Lien réservation / séjour
    booking_id = fields.Many2one("room.booking", string="Réservation")
    stay_id = fields.Many2one(
        "hotel.booking.stay", string="Séjour associé", required=True
    )

    # Informations Occupant
    first_name = fields.Char("Prénom", required=True)
    last_name = fields.Char("Nom", required=True)
    gender = fields.Selection(
        [
            ("male", "Homme"),
            ("female", "Femme"),
        ],
        string="Sexe",
    )
    date_of_birth = fields.Date("Date de naissance")
    place_of_birth = fields.Char("Lieu de naissance")
    nationality = fields.Many2one("res.country", string="Nationalité")
    street = fields.Char("Adresse")
    zip = fields.Char("Code postal")
    city = fields.Char("Ville")
    country_id = fields.Many2one("res.country", string="Pays")

    # Pièce d'identité
    id_type = fields.Selection(
        [
            ("passport", "Passeport (Étranger)"),
            ("benin_id", "Carte nationale d'identité (Bénin)"),
            ("benin_driver_license", "Permis de conduire (Bénin)"),
            ("other", "Autre pièce"),
        ],
        string="Type de pièce",
        required=True,
    )
    id_number = fields.Char("Numéro de la pièce", required=True)
    id_issue_date = fields.Date("Date de délivrance")
    id_expiry_date = fields.Date("Date d'expiration")
    id_issue_place = fields.Char("Lieu de délivrance")
    id_document_file = fields.Binary("Document scanné (PDF)", attachment=True)
    id_document_filename = fields.Char("Nom du fichier")

    # Informations Séjour
    arrival_date_time = fields.Datetime(
        "Date et Heure d'arrivée prévu",
        readonly=True,
        compute="_compute_dates",
        store=True,
        default=lambda self: self._default_arrival_date()
    )
    actual_arrival_date_time = fields.Datetime("Date et Heure d'arrivée réelle")
    departure_date_time = fields.Datetime(
        "Date et Heure de départ prévu",
        readonly=True,
        compute="_compute_dates",
        store=True,
        default=lambda self: self._default_departure_date()
    )
    actual_departure_date_time = fields.Datetime("Date et Heure de départ réel")
    number_of_guests = fields.Integer("Nombre de personnes dans la chambre")
    room_id = fields.Many2one("hotel.room", string="Chambre attribuée")

    # Informations Complémentaires
    stay_purpose = fields.Selection(
        [("business", "Affaires"), ("tourism", "Tourisme"), ("other", "Autre")],
        string="Motif du séjour",
    )
    arrival_transport = fields.Selection(
        [
            ("plane", "Avion"),
            ("train", "Train"),
            ("car", "Voiture"),
            ("other", "Autre"),
        ],
        string="Moyen de transport",
    )
    signature = fields.Binary("Signature")
    signature_date = fields.Date("Date de signature")

    # Observations
    notes = fields.Text("Observations")

    def _apply_dates_from_stay(self, rec):
        rec.arrival_date_time = rec.stay_id.planned_checkin_date if rec.stay_id else False
        rec.departure_date_time = rec.stay_id.planned_checkout_date if rec.stay_id else False
        
    @api.depends("stay_id.planned_checkin_date", "stay_id.planned_checkout_date")
    def _compute_dates(self):
        for record in self:
            print(">> COMPUTE dates for", record.stay_id, record.stay_id.planned_checkin_date, record.stay_id.planned_checkout_date)
            self._apply_dates_from_stay(record)
    
    @api.onchange("stay_id")
    def _onchange_stay_id(self):
        for record in self:
            self._apply_dates_from_stay(record)


    def _default_arrival_date(self):
        stay = self.env.context.get("default_stay_id")
        if stay:
            stay_rec = self.env["hotel.booking.stay"].browse(stay)
            return stay_rec.planned_checkin_date
        return False
    
    def _default_departure_date(self):
        stay = self.env.context.get("default_stay_id")
        if stay:
            stay_rec = self.env["hotel.booking.stay"].browse(stay)
            return stay_rec.planned_checkout_date
        return False


    def action_validate_police_form(self):
        """Valide le formulaire de police et passe au check-in"""
        if self.stay_id:
            # Appelle la méthode de check-in réelle après validation
            self.stay_id.action_start()
        return {"type": "ir.actions.act_window_close"}