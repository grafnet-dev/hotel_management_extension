from odoo import models, fields
from datetime import date

class HotelPoliceForm(models.TransientModel):
    _name = 'hotel.police.form'
    _description = 'Fiche de police pour client'

    # Lien réservation / séjour
    booking_id = fields.Many2one('room.booking', string="Réservation", required=True)
    stay_id = fields.Many2one('hotel.booking.stays', string="Séjour associé", required=True)

    # Informations Occupant
    first_name = fields.Char("Prénom", required=True)
    last_name = fields.Char("Nom", required=True)
    gender = fields.Selection([
        ('male', 'Homme'),
        ('female', 'Femme'),
    ], string="Sexe")
    date_of_birth = fields.Date("Date de naissance")
    place_of_birth = fields.Char("Lieu de naissance")
    nationality = fields.Many2one('res.country', string="Nationalité")
    street = fields.Char("Adresse")
    zip = fields.Char("Code postal")
    city = fields.Char("Ville")
    country_id = fields.Many2one('res.country', string="Pays")

    # Pièce d'identité
    id_type = fields.Selection([
        ('passport', 'Passeport (Étranger)'),
        ('benin_id', "Carte nationale d'identité (Bénin)"),
        ('benin_driver_license', 'Permis de conduire (Bénin)'),
        ('other', 'Autre pièce')
    ], string="Type de pièce", required=True)
    id_number = fields.Char("Numéro de la pièce", required=True)
    id_issue_date = fields.Date("Date de délivrance")
    id_expiry_date = fields.Date("Date d'expiration")
    id_issue_place = fields.Char("Lieu de délivrance")
    id_document_file = fields.Binary("Document scanné (PDF)", attachment=True)
    id_document_filename = fields.Char("Nom du fichier")

    # Informations Séjour
    arrival_date = fields.Date("Date d'arrivée", default=fields.Date.context_today)
    arrival_time = fields.Float("Heure d'arrivée")  # format float = heures.decimales
    departure_date = fields.Date("Date de départ prévue")
    number_of_guests = fields.Integer("Nombre de personnes dans la chambre")
    room_id = fields.Many2one('hotel.room', string="Chambre attribuée")

    # ℹInformations Complémentaires
    stay_purpose = fields.Selection([
        ('business', 'Affaires'),
        ('tourism', 'Tourisme'),
        ('other', 'Autre')
    ], string="Motif du séjour")
    arrival_transport = fields.Selection([
        ('plane', 'Avion'),
        ('train', 'Train'),
        ('car', 'Voiture'),
        ('other', 'Autre')
    ], string="Moyen de transport")
    signature = fields.Binary("Signature")
    signature_date = fields.Date("Date de signature")

    # Observations
    notes = fields.Text("Observations")


    def action_validate_police_form(self):
        """Valide le formulaire de police et passe au check-in"""
        if self.booking_id:
            # Appelle la méthode de check-in réelle après validation
            self.booking_id.action_checkin()
        return {'type': 'ir.actions.act_window_close'}