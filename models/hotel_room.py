from odoo import models, fields, api
from datetime import timedelta


class HotelRoom(models.Model):
    _inherit = "hotel.room"
    
    room_type_id = fields.Many2one( 'hotel.room.type', string="Type de chambre", required=True, ondelete="cascade")
    capacity = fields.Integer(related='room_type_id.capacity', string="capacité", readonly=True)
    bed_type = fields.Selection(related='room_type_id.bed_type', string="Type de lit", readonly=True)
    surface_area = fields.Float(related='room_type_id.surface_area', string="Superficie", readonly=True)
    max_occupancy = fields.Integer(related='room_type_id.max_occupancy', string="Capacité max", readonly=True)
    active = fields.Boolean(related='room_type_id.active',string="Actif",default=True)
    room_image_ids = fields.One2many(related='room_type_id.room_image_ids',comodel_name='hotel.room.type.image',string="Images du type de chambre",readonly=True)
    room_pricing_ids = fields.One2many('hotel.room.pricing','room_type_id',string="Prix par type de chambre",related='room_type_id.room_pricing_ids')
    reservation_type_ids = fields.Many2many('hotel.reservation.type','hotel_room_type_reservation_type_rel', 'room_type_id', 'reservation_type_id',related='room_type_id.reservation_type_ids',string="Types de réservation acceptés",help="Types de réservation que ce type de chambre peut accepter")
    reservation_slots_ids = fields.One2many(
        'hotel.room.reservation.slot',
        'room_type_id',
        related='room_type_id.reservation_slots_ids',
        string="Créneaux personnalisés"
    )
    base_price = fields.Float(related='room_type_id.base_price',string="Prix de base")
    flooring_type = fields.Selection(related='room_type_id.flooring_type', string="Type de sol")
    view_type = fields.Selection(related='room_type_id.view_type', string="Type de vue")
    is_smoking_allowed = fields.Boolean(related='room_type_id.is_smoking_allowed',string="Fumeur autorisé")
    is_pets_allowed = fields.Boolean(related='room_type_id.is_pets_allowed',string="Animaux autorisés")
    # Override the field as invisible, optional
    num_person = fields.Integer(string='Number of Persons', compute='_compute_fake', store=False)




    # booking_line_ids = flooring_type = fields.Selection([
     

 
    # Champ statut ajouté
    status = fields.Selection(selection_add=[
        ('available', 'Disponible'),
        ('occupied', 'Occupée'),
        ('cleaning', 'En nettoyage'),
        ('maintenance', 'En maintenance'),
        ('out_of_order', 'Hors service'),
        ('reserved', 'Réservée'),
    ], string="Statut", default='available')
    
    # Champ dynamique pour compter les chambres disponibles par type
    available_count = fields.Integer(
        string="Nombre de chambres disponibles",
        compute="_compute_available_count",
        store=False,
        help="Nombre de chambres disponibles pour ce type de chambre"
    )
    
    #champs à supprimer 
    price_per_night = fields.Float(string="Prix par Nuitée", digits="Product Price")
    day_use_price = fields.Float(string="Day Use Price", digits="Product Price")
    hourly_rate = fields.Float(
        string="Hourly Rate (Day Use or else )", digits="Product Price"
    )
    
    #Maintenance
    is_in_maintenance = fields.Boolean(string="Under Maintenance")
    maintenance_notes = fields.Text(string="Maintenance Notes")
    last_maintenance_date = fields.Date(string="Last Maintenance Date")
    next_maintenance_date = fields.Date(string="Next Scheduled Maintenance")
    
    reservation_type_id = fields.Many2one(
        'hotel.reservation.type', 
        string="Dummy field for view",
        compute="_compute_dummy", 
        store=False
    )

    @api.depends('room_type_id', 'status')
    def _compute_available_count(self):
        """
        Calcule le nombre de chambres disponibles par type de chambre
        """
        for record in self:
            if record.room_type_id:
                # Compte les chambres du même type avec le statut 'available'
                available_rooms = self.env['hotel.room'].search_count([
                    ('room_type_id', '=', record.room_type_id.id),
                    ('status', '=', 'available')
                ])
                record.available_count = available_rooms
            else:
                record.available_count = 0

    def _compute_dummy(self):
        for rec in self:
            rec.reservation_type_id = False

    def get_checkin_checkout_time(self, type_code=None):
        """
        Retourne les horaires à appliquer selon le type demandé.
        Si non précisé, retourne les valeurs par défaut de la chambre.
        """
        self.ensure_one()

        if type_code:
            reservation_type = self.env['hotel.reservation.type'].search([('code', '=', type_code)], limit=1)
            if reservation_type and reservation_type in self.reservation_type_ids:
                return {
                    'checkin': reservation_type.checkin_time or self.default_check_in_time,
                    'checkout': reservation_type.checkout_time or self.default_check_out_time,
                }

        return {
            'checkin': self.default_check_in_time,
            'checkout': self.default_check_out_time,
        }

    def get_timeline_with_buffer(self, buffer_duration=timedelta(hours=1)):
        """
        Cette méthode retourne une liste chronologique des réservations confirmées
        pour une chambre spécifique, en y ajoutant une marge (buffer) avant et après
        chaque réservation (ex: pour le ménage ou la préparation).
        
        :param buffer_duration: durée du buffer (par défaut 1 heure)
        :return: liste triée des réservations avec et sans buffer
        """

        # S'assure que la méthode est appelée sur une seule chambre (recordset de 1)
        self.ensure_one()

        timeline = []

        # 1. Récupère toutes les lignes de réservation confirmées pour cette chambre
        confirmed_bookings = self.env['room.booking.line'].search([
            ('room_id', '=', self.id),         # La chambre concernée
            ('state', '=', 'reserved')          # Seulement les réservations confirmées
        ])

        # 2. Parcourt chaque réservation
        for booking in confirmed_bookings:
            # Calcule la date de début avec buffer (1h avant le check-in)
            start_b = booking.checkin_date - buffer_duration
            # Calcule la date de fin avec buffer (1h après le check-out)
            end_b = booking.checkout_date + buffer_duration

            # 3. Ajoute les informations dans la timeline
            timeline.append({
                'start': booking.checkin_date,
                'end': booking.checkout_date,
                'start_buffered': start_b,
                'end_buffered': end_b,
            })

        # 4. Trie la liste par date de début avec buffer
        timeline.sort(key=lambda r: r['start_buffered'])

        return timeline

    def get_reservation_slots(self, type_code):
        self.ensure_one()
        return self.reservation_slots_ids.filtered(lambda s: s.reservation_type_id.code == type_code)

    @api.model
    def get_available_rooms_by_type(self, room_type_id):
        """
        Méthode utilitaire pour obtenir toutes les chambres disponibles d'un type donné
        """
        return self.search([
            ('room_type_id', '=', room_type_id),
            ('status', '=', 'available')
        ])

    @api.model
    def get_availability_summary(self):
        """
        Retourne un résumé de la disponibilité par type de chambre
        """
        room_types = self.env['hotel.room.type'].search([])
        summary = []
        
        for room_type in room_types:
            available_count = self.search_count([
                ('room_type_id', '=', room_type.id),
                ('status', '=', 'available')
            ])
            total_count = self.search_count([
                ('room_type_id', '=', room_type.id)
            ])
            
            summary.append({
                'room_type': room_type.name,
                'available': available_count,
                'total': total_count,
                'occupancy_rate': ((total_count - available_count) / total_count * 100) if total_count > 0 else 0
            })
        
        return summary

    # Action methods - properly indented as class methods
    def action_set_available(self):
        self.status = 'available'
        
    def action_set_occupied(self):
        self.status = 'occupied'
        
    def action_set_cleaning(self):
        self.status = 'cleaning'
        
    def action_set_maintenance(self):
        self.status = 'maintenance'
        
    def action_view_room_type_pricing(self):
        return {
            'name': 'Tarification du Type',
            'type': 'ir.actions.act_window',
            'res_model': 'hotel.room.type',
            'res_id': self.room_type_id.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_view_room_type_reservation_types(self):
        return {
            'name': 'Types de Réservation',
            'type': 'ir.actions.act_window',
            'res_model': 'hotel.room.type',
            'res_id': self.room_type_id.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_view_room_type_details(self):
        return {
            'name': 'Détails du Type de Chambre',
            'type': 'ir.actions.act_window',
            'res_model': 'hotel.room.type',
            'res_id': self.room_type_id.id,
            'view_mode': 'form',
            'target': 'new',
        }
    def _compute_fake(self):
        for rec in self:
            rec.num_person = 0  # ou rien, selon le besoin
 

#: Créer un nouveau modèle hotel.room.feature( à analyser la possibilté de le faire)
# tarification dynamque selon la periode , saison etc à ajouter
# concernant le late check out et early check in
# discounts sur les prix de nuitée et day use