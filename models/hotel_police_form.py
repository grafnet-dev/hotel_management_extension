from odoo import models, fields
from datetime import date

class HotelPoliceForm(models.TransientModel):  # ou models.Model si on veut le stocker durablement
    _name = 'hotel.police.form'
    _description = 'Fiche de police pour client'

    booking_id = fields.Many2one('room.booking', string="Réservation", required=True)

    # Identité
    guest_name = fields.Char("Nom complet", required=True)
    gender = fields.Selection([
        ('male', 'Homme'),
        ('female', 'Femme'),
        ('other', 'Autre')
    ], string="Sexe")

    date_of_birth = fields.Date("Date de naissance")
    place_of_birth = fields.Char("Lieu de naissance")
    nationality = fields.Many2one('res.country', string="Nationalité")

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

    # Pièce scannée
    id_document_file = fields.Binary("Document scanné (PDF)", attachment=True)
    id_document_filename = fields.Char("Nom du fichier")

    # Infos séjour
    arrival_date = fields.Date("Date d'arrivée", default=fields.Date.context_today)
    departure_date = fields.Date("Date de départ")
    room_number = fields.Char("Numéro de chambre (optionnel)")

    # Observations ou remarques
    notes = fields.Text("Observations")

    def action_validate_police_form(self):
        """Valide le formulaire de police et passe au check-in"""
        if self.booking_id:
            # Appelle la méthode de check-in réelle après validation
            self.booking_id.action_checkin()
        return {'type': 'ir.actions.act_window_close'}