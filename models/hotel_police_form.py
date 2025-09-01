from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import date

class HotelPoliceForm(models.TransientModel):
    _name = 'hotel.police.form'
    _description = 'Fiche de police pour client'

    booking_id = fields.Many2one('room.booking', string="Réservation", required=True)
    
    # Liaison avec les clients hôtel
    partner_id = fields.Many2one(
        'res.partner', 
        string="Client", 
        domain=[('is_hotel_client', '=', True)],
        help="Sélectionnez un client existant ou créez-en un nouveau"
    )
    
    # Mode de saisie
    use_existing_client = fields.Boolean(
        string="Utiliser un client existant", 
        default=True,
        help="Cochez pour sélectionner un client existant, décochez pour créer un nouveau"
    )

    # Identité - AUCUN CHAMP REQUIRED pour éviter les erreurs !
    guest_name = fields.Char("Nom complet")
    gender = fields.Selection([
        ('male', 'Homme'),
        ('female', 'Femme'),
        ('other', 'Autre')
    ], string="Sexe")

    date_of_birth = fields.Date("Date de naissance")
    place_of_birth = fields.Char("Lieu de naissance")
    nationality = fields.Many2one('res.country', string="Nationalité")

    # Pièce d'identité - AUCUN CHAMP REQUIRED !
    id_type = fields.Selection([
        ('cni', "Carte Nationale d'Identité"),
        ('passport', "Passeport"),
        ('permis', "Permis de Conduire"),
        ('carte_sejour', "Carte de Séjour"),
        ('other', "Autre")
    ], string="Type de pièce")

    id_number = fields.Char("Numéro de la pièce")
    id_issue_date = fields.Date("Date de délivrance")
    id_expiry_date = fields.Date("Date d'expiration")
    id_issue_place = fields.Char("Lieu de délivrance")

    # Contact d'urgence
    emergency_contact_name = fields.Char("Contact d'urgence")
    emergency_contact_phone = fields.Char("Téléphone d'urgence")

    # Pièce scannée
    id_document_file = fields.Binary("Document scanné (PDF)", attachment=True)
    id_document_filename = fields.Char("Nom du fichier")

    # Infos séjour
    arrival_date = fields.Date("Date d'arrivée", default=fields.Date.context_today)
    departure_date = fields.Date("Date de départ")
    room_number = fields.Char("Numéro de chambre (optionnel)")

    # Observations
    notes = fields.Text("Observations")

    # Champs calculés pour les alertes
    document_expired = fields.Boolean("Document expiré", compute="_compute_document_status")
    is_minor = fields.Boolean("Mineur", compute="_compute_age_info")
    
    @api.depends('partner_id')
    def _compute_document_status(self):
        """Vérifie si le document du client est expiré"""
        for record in self:
            if record.partner_id and hasattr(record.partner_id, 'document_expired'):
                record.document_expired = record.partner_id.document_expired
            else:
                record.document_expired = False
    
    @api.depends('partner_id', 'date_of_birth')
    def _compute_age_info(self):
        """Vérifie si le client est mineur"""
        for record in self:
            if record.partner_id and hasattr(record.partner_id, 'is_adult'):
                record.is_minor = not record.partner_id.is_adult
            elif record.date_of_birth:
                today = fields.Date.today()
                age = today.year - record.date_of_birth.year
                if today.month < record.date_of_birth.month or \
                   (today.month == record.date_of_birth.month and today.day < record.date_of_birth.day):
                    age -= 1
                record.is_minor = age < 18
            else:
                record.is_minor = False

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        """Auto-remplit les champs quand on sélectionne un client"""
        if self.partner_id:
            partner = self.partner_id
            self.guest_name = partner.name
            
            # Vérifier si les champs existent avant de les assigner
            if hasattr(partner, 'birth_date'):
                self.date_of_birth = partner.birth_date
            if hasattr(partner, 'nationality_id'):
                self.nationality = partner.nationality_id
            if hasattr(partner, 'document_type'):
                self.id_type = partner.document_type
            if hasattr(partner, 'document_number'):
                self.id_number = partner.document_number
            if hasattr(partner, 'document_issue_date'):
                self.id_issue_date = partner.document_issue_date
            if hasattr(partner, 'document_expiry_date'):
                self.id_expiry_date = partner.document_expiry_date
            if hasattr(partner, 'document_issue_place'):
                self.id_issue_place = partner.document_issue_place
            if hasattr(partner, 'emergency_contact_name'):
                self.emergency_contact_name = partner.emergency_contact_name
            if hasattr(partner, 'emergency_contact_phone'):
                self.emergency_contact_phone = partner.emergency_contact_phone

    @api.onchange('use_existing_client')
    def _onchange_use_existing_client(self):
        """Efface les champs quand on change de mode"""
        if not self.use_existing_client:
            self.partner_id = False
            # Vider les champs pour nouveau client
            self.guest_name = ""
            self.date_of_birth = False
            self.nationality = False
            self.id_type = False
            self.id_number = ""
            self.emergency_contact_name = ""
            self.emergency_contact_phone = ""

    def action_open_new_client_form(self):
        """Ouvre le formulaire de création de nouveau client"""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Nouveau Client Hôtel',
            'res_model': 'res.partner',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_is_hotel_client': True,
                'default_customer_rank': 1,
                'default_name': self.guest_name or "",
                'default_document_type': self.id_type or False,
                'default_document_number': self.id_number or "",
                'default_birth_date': self.date_of_birth or False,
                'default_nationality_id': self.nationality.id if self.nationality else False,
            }
        }

    def action_create_new_client(self):
        """Crée un nouveau client avec les informations saisies"""
        # Validation minimale pour nouveau client
        if not self.guest_name:
            raise ValidationError("Le nom du client est obligatoire pour créer un nouveau client.")
        
        if not self.id_type:
            raise ValidationError("Le type de document est obligatoire pour créer un nouveau client.")
            
        if not self.id_number:
            raise ValidationError("Le numéro de document est obligatoire pour créer un nouveau client.")

        # Créer le nouveau client
        client_vals = {
            'name': self.guest_name,
            'is_hotel_client': True,
            'customer_rank': 1,
        }
        
        # Ajouter les champs optionnels s'ils existent
        if self.date_of_birth:
            client_vals['birth_date'] = self.date_of_birth
        if self.nationality:
            client_vals['nationality_id'] = self.nationality.id
        if self.id_type:
            client_vals['document_type'] = self.id_type
        if self.id_number:
            client_vals['document_number'] = self.id_number
        if self.id_issue_date:
            client_vals['document_issue_date'] = self.id_issue_date
        if self.id_expiry_date:
            client_vals['document_expiry_date'] = self.id_expiry_date
        if self.id_issue_place:
            client_vals['document_issue_place'] = self.id_issue_place
        if self.emergency_contact_name:
            client_vals['emergency_contact_name'] = self.emergency_contact_name
        if self.emergency_contact_phone:
            client_vals['emergency_contact_phone'] = self.emergency_contact_phone

        try:
            new_client = self.env['res.partner'].create(client_vals)
            self.partner_id = new_client
            self.use_existing_client = True  # Basculer en mode client existant
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': f"Nouveau client '{self.guest_name}' créé avec succès !",
                    'type': 'success',
                }
            }
        except Exception as e:
            raise ValidationError(f"Erreur lors de la création du client : {str(e)}")

    def action_validate_police_form(self):
        """Valide le formulaire de police et effectue le check-in"""
        
        # VALIDATION PRINCIPALE
        if self.use_existing_client:
            # Mode client existant
            if not self.partner_id:
                raise ValidationError("Veuillez sélectionner un client existant.")
        else:
            # Mode nouveau client - créer d'abord le client
            if not self.partner_id:
                self.action_create_new_client()
        
        # S'assurer qu'on a un client maintenant
        if not self.partner_id:
            raise ValidationError("Aucun client sélectionné ou créé.")

        # Validation des dates de séjour
        if not self.arrival_date:
            raise ValidationError("La date d'arrivée est obligatoire.")
            
        if self.departure_date and self.arrival_date >= self.departure_date:
            raise ValidationError("La date de départ doit être après la date d'arrivée.")

        # Lier le client à la réservation
        try:
            if self.booking_id and hasattr(self.booking_id, 'partner_id'):
                self.booking_id.write({'partner_id': self.partner_id.id})
            
            # Message de succès
            message = f"Fiche de police validée pour {self.partner_id.name}"
            
            # Effectuer le check-in
            if self.booking_id and hasattr(self.booking_id, 'action_checkin'):
                self.booking_id.action_checkin()
                
                # Notification de succès
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': "✅ Check-in Réussi",
                        'message': f"{self.partner_id.name} a bien été enregistré",
                        'type': 'success',
                        'sticky': False,
                    }
                }
            else:
                # Si pas de méthode action_checkin, juste fermer
                return {'type': 'ir.actions.act_window_close'}
                
        except Exception as e:
            raise ValidationError(f"Erreur lors du check-in : {str(e)}")