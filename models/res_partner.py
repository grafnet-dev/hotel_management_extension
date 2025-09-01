# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import date, timedelta

class ResPartner(models.Model):
    _inherit = 'res.partner'

    # === INFORMATIONS D'IDENTITÉ ===
    document_type = fields.Selection([
        ('cni', "Carte Nationale d'Identité"),
        ('passport', "Passeport"),
        ('permis', "Permis de Conduire"),
        ('carte_sejour', "Carte de Séjour"),
        ('other', "Autre")
    ], string="Type de Document d'Identité")

    document_number = fields.Char(
        string="Numéro de Document",
        help="Numéro unique du document d'identité"
    )
    
    document_issue_date = fields.Date(
        string="Date de Délivrance",
        help="Date à laquelle le document a été délivré"
    )
    
    document_expiry_date = fields.Date(
        string="Date d'Expiration",
        help="Date d'expiration du document"
    )
    
    document_issue_place = fields.Char(
        string="Lieu de Délivrance",
        help="Ville ou lieu où le document a été délivré"
    )
    
    issuing_authority = fields.Char(
        string="Autorité de Délivrance",
        help="Organisme qui a délivré le document"
    )

    # === INFORMATIONS PERSONNELLES ===
    birth_date = fields.Date(
        string="Date de Naissance",
        help="Date de naissance pour vérification d'âge"
    )
    
    age = fields.Integer(
        string="Âge",
        compute="_compute_age",
        store=True,
        help="Âge calculé automatiquement"
    )
    
    is_adult = fields.Boolean(
        string="Majeur (+18 ans)",
        compute="_compute_age",
        store=True
    )
    
    profession = fields.Char(
        string="Profession",
        help="Profession ou activité principale"
    )
    
    nationality_id = fields.Many2one(
        'res.country',
        string="Nationalité",
        help="Pays de nationalité"
    )

    # === CONTACT D'URGENCE ===
    emergency_contact_name = fields.Char(
        string="Personne à Contacter en Urgence",
        help="Nom complet de la personne à contacter"
    )
    
    emergency_contact_phone = fields.Char(
        string="Téléphone d'Urgence",
        help="Numéro de téléphone de la personne à contacter"
    )
    
    emergency_contact_relation = fields.Selection([
        ('parent', 'Parent'),
        ('conjoint', 'Conjoint(e)'),
        ('enfant', 'Enfant'),
        ('ami', 'Ami(e)'),
        ('collegue', 'Collègue'),
        ('other', 'Autre')
    ], string="Relation avec Contact d'Urgence")

    # === INFORMATIONS HÔTEL ===
    is_hotel_client = fields.Boolean(
        string="Client Hôtel",
        default=False,
        help="Cocher si c'est un client de l'hôtel"
    )
    
    visit_purpose = fields.Selection([
        ('business', 'Affaires'),
        ('tourism', 'Tourisme'),
        ('family', 'Visite Familiale'),
        ('medical', 'Médical'),
        ('conference', 'Conférence/Séminaire'),
        ('other', 'Autre')
    ], string="Motif du Séjour")
    
    special_requests = fields.Text(
        string="Demandes Spéciales",
        help="Allergies, préférences alimentaires, handicaps, etc."
    )
    
    # === CHAMPS TECHNIQUES ===
    document_expires_soon = fields.Boolean(
    string="Document expire bientôt",
    compute="_compute_expiry_warnings",
    store=True,
    index=True,  # Ajoutez cette ligne
    help="Alerte si le document expire dans 30 jours"
)

    document_expired = fields.Boolean(
    string="Document expiré",
    compute="_compute_expiry_warnings",
    store=True,
    index=True,  # Ajoutez cette ligne
    help="True si le document est expiré"
)
    
    check_in_count = fields.Integer(
        string="Nombre de Check-ins",
        compute="_compute_hotel_stats",
        help="Nombre total de séjours"
    )

    # === MÉTHODES CALCULÉES ===
    @api.depends('birth_date')
    def _compute_age(self):
        """Calcule l'âge et vérifie la majorité"""
        today = date.today()
        for partner in self:
            if partner.birth_date:
                age = today.year - partner.birth_date.year
                # Ajustement si l'anniversaire n'est pas encore passé
                if today.month < partner.birth_date.month or \
                   (today.month == partner.birth_date.month and today.day < partner.birth_date.day):
                    age -= 1
                partner.age = age
                partner.is_adult = age >= 18
            else:
                partner.age = 0
                partner.is_adult = False

    @api.depends('document_expiry_date')
    def _compute_expiry_warnings(self):
        """Calcule les alertes d'expiration"""
        today = date.today()
        for partner in self:
            if partner.document_expiry_date:
                days_diff = (partner.document_expiry_date - today).days
                partner.document_expired = days_diff < 0
                partner.document_expires_soon = 0 <= days_diff <= 30
            else:
                partner.document_expired = False
                partner.document_expires_soon = False

    def _compute_hotel_stats(self):
        """Calcule les statistiques hôtel (préparation pour module hôtel)"""
        for partner in self:
            # Pour l'instant, on met 0. Sera remplacé quand le module hôtel sera créé
            partner.check_in_count = 0

    # === CONTRAINTES ET VALIDATIONS ===
    @api.constrains('document_issue_date', 'document_expiry_date')
    def _check_document_dates(self):
        """Valide les dates du document"""
        for partner in self:
            if partner.document_issue_date and partner.document_expiry_date:
                if partner.document_expiry_date <= partner.document_issue_date:
                    raise ValidationError(
                        _("La date d'expiration doit être postérieure à la date de délivrance.")
                    )

    @api.constrains('birth_date')
    def _check_birth_date(self):
        """Valide la date de naissance"""
        today = date.today()
        for partner in self:
            if partner.birth_date:
                if partner.birth_date > today:
                    raise ValidationError(
                        _("La date de naissance ne peut pas être dans le futur.")
                    )
                if partner.birth_date < date(1900, 1, 1):
                    raise ValidationError(
                        _("La date de naissance semble incorrecte.")
                    )

    @api.constrains('document_number', 'document_type')
    def _check_document_number_unique(self):
        """Vérifie l'unicité du numéro de document"""
        for partner in self:
            if partner.document_number and partner.document_type:
                existing = self.search([
                    ('document_number', '=', partner.document_number),
                    ('document_type', '=', partner.document_type),
                    ('id', '!=', partner.id)
                ])
                if existing:
                    raise ValidationError(
                        _("Ce numéro de document existe déjà pour ce type de document.")
                    )

    # === MÉTHODES UTILITAIRES ===
    def action_validate_document(self):
        """Action pour valider un document (bouton dans la vue)"""
        self.ensure_one()
        if not self.document_number:
            raise ValidationError(_("Aucun numéro de document à valider."))
        
        # Ici on pourrait ajouter une logique de validation externe
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': _("Document validé avec succès."),
                'type': 'success',
            }
        }

    def get_hotel_info_summary(self):
        """Retourne un résumé des informations hôtel"""
        self.ensure_one()
        info = []
        if self.document_type and self.document_number:
            info.append(f"{dict(self._fields['document_type'].selection)[self.document_type]}: {self.document_number}")
        if self.profession:
            info.append(f"Profession: {self.profession}")
        if self.visit_purpose:
            info.append(f"Motif: {dict(self._fields['visit_purpose'].selection)[self.visit_purpose]}")
        return " | ".join(info)

    # === ACTIONS AUTOMATIQUES ===
    @api.model
    def create(self, vals):
        """Override create pour logique spécifique hôtel"""
        # Si c'est un client hôtel, on s'assure que certains champs sont requis
        if vals.get('is_hotel_client'):
            if not vals.get('birth_date'):
                # On pourrait forcer la saisie ou donner un avertissement
                pass
        
        return super(ResPartner, self).create(vals)
    def action_open_police_form(self):
     
        self.ensure_one()
        return {
            'name': _('Fiche Police'),
            'type': 'ir.actions.act_window',
            'res_model': 'hotel.police.form',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_partner_id': self.id,
                'default_guest_name': self.name,
                'default_gender': self.gender,
                'default_date_of_birth': self.birth_date,
                'default_nationality': self.nationality_id.id,
                'default_id_type': self.document_type,
                'default_id_number': self.document_number,
                'default_id_issue_date': self.document_issue_date,
                'default_id_expiry_date': self.document_expiry_date,
                'default_id_issue_place': self.document_issue_place,
            }
        }
    

    def write(self, vals):
        """Override write pour logique spécifique hôtel"""
        result = super(ResPartner, self).write(vals)
        
        # Si on modifie le statut client hôtel
        if 'is_hotel_client' in vals:
            # On pourrait déclencher des actions spécifiques
            pass
            
        return result