# -*- coding: utf-8 -*-
from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class HotelHousekeeping(models.Model):
    _name = 'hotel.housekeeping'
    _description = 'Gestion du nettoyage des chambres'
    _order = 'create_date desc'

    # Relations
    stay_id = fields.Many2one(
        'hotel.booking.stay', 
        string='Séjour', 
        required=True,
        ondelete='cascade'
    )
    room_id = fields.Many2one(
        'hotel.room', 
        string='Chambre', 
        required=True,
        ondelete='cascade'
    )
    task_id = fields.Many2one(
        'project.task', 
        string='Tâche de nettoyage',
        ondelete='set null'
    )

    # Planning
    planned_hours = fields.Float(
        string='Durée estimée (h)', 
        default=0.5,
        help="Temps estimé pour nettoyer cette chambre"
    )
    start_datetime = fields.Datetime(string='Début nettoyage')
    end_datetime = fields.Datetime(string='Fin nettoyage')

    # Suivi d'état
    state = fields.Selection([
        ('waiting', 'En attente'),
        ('in_progress', 'En cours'),
        ('inspection', 'En inspection'),
        ('done', 'Terminé'),
    ], string='État', default='waiting', required=True)

    # Infos supplémentaires
    notes = fields.Text(string='Notes')

    @api.model
    def _get_or_create_housekeeping_project(self):
        """Récupère ou crée le projet Housekeeping avec ses stages"""
        Project = self.env['project.project']
        Stage = self.env['project.task.type']
        
        # Chercher le projet
        project = Project.search([('name', '=', 'Nettoyage Hôtel')], limit=1)
        
        if not project:
            # Créer le projet
            project = Project.create({
                'name': 'Nettoyage Hôtel',
                'allow_timesheets': True,
            })
            _logger.info("📁 [HOUSEKEEPING] Projet créé : ID=%s", project.id)
            
            # Créer les stages
            stages_data = [
                {'name': 'À faire', 'sequence': 1, 'fold': False},
                {'name': 'En cours', 'sequence': 2, 'fold': False},
                {'name': 'Inspection', 'sequence': 3, 'fold': False},
                {'name': 'Terminé', 'sequence': 4, 'fold': True},
            ]
            
            for stage_data in stages_data:
                Stage.create({
                    **stage_data,
                    'project_ids': [(4, project.id)],
                })
            
            _logger.info("✅ [HOUSEKEEPING] 4 stages créés pour le projet")
        
        return project

    def create_housekeeping_task(self):
        """Crée la tâche project.task associée"""
        self.ensure_one()
        _logger.info("📋 [HOUSEKEEPING] Création tâche pour housekeeping=%s", self.id)
        
        # Récupérer ou créer le projet
        project = self._get_or_create_housekeeping_project()
        
        # Récupérer le premier stage "À faire"
        stage_todo = self.env['project.task.type'].search([
            ('project_ids', 'in', [project.id]),
            ('name', '=', 'À faire')
        ], limit=1)
        
        # Récupérer les infos du séjour de manière sécurisée
        guest_name = "N/A"
        checkout_date = "N/A"
        room_type = "N/A"
        booking_ref = "N/A"
        
        try:
            if self.stay_id:
                # Utiliser occupant_names au lieu de guest_id.name
                guest_name = self.stay_id.occupant_names or "N/A"
                
                # Utiliser planned_checkout_date au lieu de check_out_date
                if self.stay_id.planned_checkout_date:
                    checkout_date = str(self.stay_id.planned_checkout_date)
                
                # Type de chambre
                if self.stay_id.room_type_id:
                    room_type = self.stay_id.room_type_id.name
                
                # Référence booking
                if self.stay_id.booking_id:
                    booking_ref = self.stay_id.booking_id.name or f"ID-{self.stay_id.booking_id.id}"
        except Exception as e:
            _logger.warning("⚠️ [HOUSEKEEPING] Erreur lors de la récupération des infos du séjour: %s", e)
        
        # Créer la tâche
        task_vals = {
            'name': f"Nettoyage chambre {self.room_id.name}",
            'project_id': project.id,
            'stage_id': stage_todo.id if stage_todo else False,
            'description': f"""
                <p><strong>Réservation :</strong> {booking_ref}</p>
                <p><strong>Occupants :</strong> {guest_name}</p>
                <p><strong>Checkout :</strong> {checkout_date}</p>
                <p><strong>Type chambre :</strong> {room_type}</p>
            """,
            'x_room_id': self.room_id.id,
            'x_stay_id': self.stay_id.id,
            'x_housekeeping_id': self.id,
        }
        
        try:
            task = self.env['project.task'].create(task_vals)
            self.task_id = task.id
            _logger.info("✅ [HOUSEKEEPING] Tâche créée : ID=%s | %s", task.id, task.name)
            return task
        except Exception as e:
            _logger.exception("❌ [HOUSEKEEPING] Erreur lors de la création de la tâche: %s", e)
            raise