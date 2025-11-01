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
        default=0.5
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

    notes = fields.Text(string='Notes')

    @api.model_create_multi
    def create(self, vals_list):
        """Création avec logs détaillés"""
        _logger.info("="*80)
        _logger.info("🔥 [HOUSEKEEPING CREATE] Début création de %s enregistrements", len(vals_list))
        
        for idx, vals in enumerate(vals_list):
            _logger.info("📝 Record %s/%s: %s", idx+1, len(vals_list), vals)
        
        # Création standard
        records = super().create(vals_list)
        
        _logger.info("✅ [HOUSEKEEPING CREATE] %s records créés", len(records))
        
        # Créer les tâches pour chaque record
        for record in records:
            _logger.info("🔄 [HOUSEKEEPING CREATE] Traitement record ID=%s", record.id)
            
            if not record.task_id:
                _logger.info("🎯 [HOUSEKEEPING CREATE] Appel create_housekeeping_task pour ID=%s", record.id)
                try:
                    task = record.create_housekeeping_task()
                    if task:
                        _logger.info("✅ [HOUSEKEEPING CREATE] Tâche créée: ID=%s", task.id)
                    else:
                        _logger.error("❌ [HOUSEKEEPING CREATE] create_housekeeping_task a retourné None!")
                except Exception as e:
                    _logger.error("❌ [HOUSEKEEPING CREATE] Exception: %s", e, exc_info=True)
            else:
                _logger.info("ℹ️ [HOUSEKEEPING CREATE] Tâche déjà existante ID=%s", record.task_id.id)
        
        _logger.info("="*80)
        return records

    def create_housekeeping_task(self):
        """Crée la tâche project.task - VERSION COMPATIBLE TOUTES VERSIONS ODOO"""
        self.ensure_one()
        
        _logger.info("="*80)
        _logger.info("🎯 [CREATE TASK] Début pour housekeeping ID=%s", self.id)
        _logger.info("   - stay_id: %s", self.stay_id.id if self.stay_id else None)
        _logger.info("   - room_id: %s (nom: %s)", self.room_id.id if self.room_id else None, self.room_id.name if self.room_id else None)
        
        # Vérifier si une tâche existe déjà
        if self.task_id:
            _logger.warning("⚠️ [CREATE TASK] Tâche déjà existante ID=%s", self.task_id.id)
            return self.task_id
        
        # Récupérer ou créer le projet
        _logger.info("📁 [CREATE TASK] Récupération du projet...")
        try:
            project = self._get_or_create_housekeeping_project()
            _logger.info("✅ [CREATE TASK] Projet trouvé/créé: ID=%s (%s)", project.id, project.name)
        except Exception as e:
            _logger.error("❌ [CREATE TASK] Erreur récupération projet: %s", e, exc_info=True)
            raise
        
        # Récupérer le stage "À faire"
        _logger.info("🔍 [CREATE TASK] Recherche stage 'À faire'...")
        stage_todo = self.env['project.task.type'].search([
            ('project_ids', 'in', [project.id]),
            ('name', '=', 'À faire')
        ], limit=1)
        
        if not stage_todo:
            _logger.error("❌ [CREATE TASK] Stage 'À faire' introuvable!")
            stage_todo = self.env['project.task.type'].search([
                ('project_ids', 'in', [project.id])
            ], limit=1, order='sequence')
            _logger.info("🔄 [CREATE TASK] Utilisation du premier stage disponible: %s", stage_todo.name if stage_todo else "AUCUN")
        else:
            _logger.info("✅ [CREATE TASK] Stage trouvé: ID=%s (%s)", stage_todo.id, stage_todo.name)
        
        # Préparer les valeurs de la tâche - VERSION MINIMALISTE
        task_vals = {
            'name': f"Nettoyage chambre {self.room_id.name}",
            'project_id': project.id,
            'stage_id': stage_todo.id if stage_todo else False,
            'description': f"<p>Nettoyage après checkout</p><p>Séjour: {self.stay_id.id}</p>",
            # Champs personnalisés
            'room_id': self.room_id.id,
            'stay_id': self.stay_id.id,
            'housekeeping_id': self.id,
            # SUPPRIMÉ : 'planned_hours': self.planned_hours or 0.5,  # Ce champ n'existe pas dans toutes les versions
        }
        
        _logger.info("📝 [CREATE TASK] Valeurs de la tâche:")
        for key, val in task_vals.items():
            _logger.info("   - %s: %s", key, val)
        
        # Créer la tâche
        try:
            _logger.info("🚀 [CREATE TASK] Appel project.task.create()...")
            task = self.env['project.task'].create(task_vals)
            _logger.info("✅ [CREATE TASK] Tâche créée: ID=%s", task.id)
            
            # Lier la tâche au housekeeping
            self.task_id = task.id
            _logger.info("🔗 [CREATE TASK] Tâche liée au housekeeping")
            
            # Invalider le cache
            self.invalidate_recordset()
            task.invalidate_recordset()
            
            _logger.info("="*80)
            return task
            
        except Exception as e:
            _logger.error("❌ [CREATE TASK] Erreur création tâche: %s", e, exc_info=True)
            raise

    def _get_or_create_housekeeping_project(self):
        """Récupère ou crée le projet 'Nettoyage Hôtel' - VERSION COMPATIBLE TOUTES VERSIONS"""
        _logger.info("🔍 [GET PROJECT] Recherche du projet 'Nettoyage Hôtel'...")
        
        project = self.env['project.project'].search([
            ('name', '=', 'Nettoyage Hôtel')
        ], limit=1)
        
        if project:
            _logger.info("✅ [GET PROJECT] Projet existant: ID=%s", project.id)
            return project
        
        _logger.info("📁 [GET PROJECT] Création du projet...")
        
        # Créer le projet SANS allow_subtasks
        project = self.env['project.project'].create({
            'name': 'Nettoyage Hôtel',
            # SUPPRIMÉ : 'allow_subtasks': False,  # Ce champ n'existe pas dans toutes les versions
        })
        _logger.info("✅ [GET PROJECT] Projet créé: ID=%s", project.id)
        
        # Créer les stages
        stages_data = [
            {'name': 'À faire', 'sequence': 1, 'fold': False},
            {'name': 'En cours', 'sequence': 2, 'fold': False},
            {'name': 'Inspection', 'sequence': 3, 'fold': False},
            {'name': 'Terminé', 'sequence': 4, 'fold': True},
        ]
        
        for stage_vals in stages_data:
            stage = self.env['project.task.type'].create({
                'name': stage_vals['name'],
                'sequence': stage_vals['sequence'],
                'fold': stage_vals['fold'],
                'project_ids': [(4, project.id)]
            })
            _logger.info("✅ [GET PROJECT] Stage créé: %s (ID=%s)", stage.name, stage.id)
        
        return project