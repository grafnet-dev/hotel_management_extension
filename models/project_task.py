# -*- coding: utf-8 -*-
from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class ProjectTaskHousekeeping(models.Model):
    _inherit = 'project.task'

    # Champs custom pour housekeeping
    x_room_id = fields.Many2one('hotel.room', string='Chambre')
    x_stay_id = fields.Many2one('hotel.booking.stay', string='Séjour')
    x_housekeeping_id = fields.Many2one('hotel.housekeeping', string='Lien Housekeeping')
    
    # Contrôle qualité
    x_inspected = fields.Boolean(string='Inspecté', default=False)
    
    # Timing
    x_start_datetime = fields.Datetime(string='Début réel')
    x_end_datetime = fields.Datetime(string='Fin réelle')
    
    # Notes supplémentaires
    x_notes = fields.Text(string='Notes de nettoyage')

    def action_start_cleaning(self):
        """Bouton : Démarrer le nettoyage"""
        self.ensure_one()
        _logger.info("🧹 [START] Début nettoyage tâche=%s", self.id)
        
        # Enregistrer l'heure de début
        self.x_start_datetime = fields.Datetime.now()
        
        # Passer au stage "En cours"
        stage_in_progress = self.env['project.task.type'].search([
            ('project_ids', 'in', [self.project_id.id]),
            ('name', '=', 'En cours')
        ], limit=1)
        if stage_in_progress:
            self.stage_id = stage_in_progress
        
        # Mettre à jour la chambre
        if self.x_room_id:
            self.x_room_id.state = 'cleaning'
        
        # Mettre à jour le housekeeping
        if self.x_housekeeping_id:
            self.x_housekeeping_id.state = 'in_progress'
            self.x_housekeeping_id.start_datetime = self.x_start_datetime
        
        # Notification
        self.message_post(
            body=f"🧹 Nettoyage démarré par {self.env.user.name}",
            message_type='notification'
        )
        
        return True

    def action_inspection_ok(self):
        """Bouton : Valider l'inspection"""
        self.ensure_one()
        _logger.info("✅ [INSPECTION] Validation tâche=%s", self.id)
        
        # Marquer comme inspecté
        self.x_inspected = True
        self.x_end_datetime = fields.Datetime.now()
        
        # Passer au stage "Terminé"
        stage_done = self.env['project.task.type'].search([
            ('project_ids', 'in', [self.project_id.id]),
            ('name', '=', 'Terminé')
        ], limit=1)
        if stage_done:
            self.stage_id = stage_done
        
        # Mettre à jour la chambre
        if self.x_room_id:
            self.x_room_id.state = 'available'
        
        # Mettre à jour le housekeeping
        if self.x_housekeeping_id:
            self.x_housekeeping_id.state = 'done'
            self.x_housekeeping_id.end_datetime = self.x_end_datetime
        
        # Notification
        self.message_post(
            body=f"✅ Inspection validée par {self.env.user.name} - Chambre disponible",
            message_type='notification'
        )
        
        return True

    @api.model_create_multi
    def create(self, vals_list):
        """Surcharge de la création pour auto-abonner les responsables"""
        tasks = super().create(vals_list)
        
        for task in tasks:
            # Si c'est une tâche housekeeping
            if task.project_id.name == 'Nettoyage Hôtel':
                # Abonner le responsable du projet
                if task.project_id.user_id:
                    task.message_subscribe(partner_ids=[task.project_id.user_id.partner_id.id])
        
        return tasks

    def write(self, vals):
        """Notification lors du changement de stage"""
        res = super().write(vals)
        
        if 'stage_id' in vals:
            for task in self:
                if task.project_id.name == 'Nettoyage Hôtel':
                    stage_name = task.stage_id.name
                    
                    # Notification selon le stage
                    if stage_name == 'En cours':
                        task.message_post(
                            body=f"🧹 Nettoyage en cours - Agent: {task.user_ids[0].name if task.user_ids else 'Non assigné'}",
                            message_type='notification'
                        )
                    elif stage_name == 'Inspection':
                        task.message_post(
                            body=f"🔍 Nettoyage terminé, en attente d'inspection",
                            message_type='notification'
                        )
                    elif stage_name == 'Terminé':
                        task.message_post(
                            body=f"✅ Chambre {task.x_room_id.name} validée et disponible",
                            message_type='notification'
                        )
        
        return res