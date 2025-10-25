from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class ProjectTaskHousekeeping(models.Model):
    _inherit = 'project.task'

    # ============ CHAMPS OBLIGATOIRES MANQUANTS ============
    
    x_room_id = fields.Many2one(
        'hotel.room',
        string='Chambre',
        help='Chambre à nettoyer',
        index=True  # Important pour les performances
    )
    
    x_stay_id = fields.Many2one(
        'hotel.booking.stay',
        string='Séjour',
        help='Séjour associé',
        index=True
    )
    
    x_housekeeping_id = fields.Many2one(
        'hotel.housekeeping',
        string='Housekeeping',
        help='Enregistrement housekeeping',
        ondelete='cascade',
        index=True
    )
    
    x_start_datetime = fields.Datetime(
        string='Début nettoyage'
    )
    
    x_end_datetime = fields.Datetime(
        string='Fin nettoyage'
    )
    
    x_inspected = fields.Boolean(
        string='Inspecté',
        default=False
    )
    
    x_notes = fields.Text(
        string='Notes'
    )

    # ============ MÉTHODES ============
    
    def action_start_cleaning(self):
        """Démarrer le nettoyage"""
        self.ensure_one()
        _logger.info("🧹 [START] Tâche=%s", self.id)
        
        self.x_start_datetime = fields.Datetime.now()
        
        # Changer le stage
        stage = self.env['project.task.type'].search([
            ('project_ids', 'in', [self.project_id.id]),
            ('name', '=', 'En cours')
        ], limit=1)
        
        if stage:
            self.stage_id = stage.id
        
        # Mettre à jour la chambre
        if self.x_room_id:
            self.x_room_id.status = 'cleaning'
        
        # Mettre à jour housekeeping
        if self.x_housekeeping_id:
            self.x_housekeeping_id.write({
                'state': 'in_progress',
                'start_datetime': self.x_start_datetime
            })
        
        self.message_post(body=f"🧹 Démarré par {self.env.user.name}")
        return True

    def action_inspection_ok(self):
        """Valider l'inspection"""
        self.ensure_one()
        _logger.info("✅ [INSPECTION] Tâche=%s", self.id)
        
        self.x_inspected = True
        self.x_end_datetime = fields.Datetime.now()
        
        # Changer le stage
        stage = self.env['project.task.type'].search([
            ('project_ids', 'in', [self.project_id.id]),
            ('name', '=', 'Terminé')
        ], limit=1)
        
        if stage:
            self.stage_id = stage.id
        
        # Mettre à jour la chambre
        if self.x_room_id:
            self.x_room_id.status = 'available'
        
        # Mettre à jour housekeeping
        if self.x_housekeeping_id:
            self.x_housekeeping_id.write({
                'state': 'done',
                'end_datetime': self.x_end_datetime
            })
        
        self.message_post(body=f"✅ Validé par {self.env.user.name}")
        return True