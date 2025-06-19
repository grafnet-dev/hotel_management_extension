from odoo import models, fields
from datetime import timedelta


class HotelRoom(models.Model):
    _inherit = "hotel.room"
    
    #image principale et galerie 
    image = fields.Binary(string="Image", attachment=True)
    room_image_ids = fields.One2many('hotel.room.image', 'room_id', string="Room Images")
    
    # Type de réservation
    reservation_type_ids = fields.Many2many(
    'hotel.reservation.type',
    'hotel_room_reservation_type_rel',  # nom de la table relation
    'room_id',
    'reservation_type_id',
    string="Types de réservation disponibles",
    help="Liste des types de réservation que cette chambre accepte"
    )

    reservation_slots_ids = fields.One2many(
    'hotel.room.reservation.slot',
    'room_id',
    string="Créneaux personnalisés"
   )
    
    #Heure limite pour early check-in et late check-out
    
    early_checkin_hour_limit = fields.Float(
    string="Heure limite Early Check-in",
    default=6.0,
    help="En dessous de cette heure, l'early check-in est considéré comme une nuit supplémentaire."
    )

    late_checkout_hour_limit = fields.Float(
        string="Heure limite Late Check-out",
        default=18.0,
        help="Au-dessus de cette heure, le late check-out est considéré comme une nuit supplémentaire."
    )
    
    # Tarification
    
    room_pricing_ids = fields.One2many(
    'hotel.room.pricing',
    'room_id',
    string="Tarifications par type"
    )

    
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
    
    # feature (caractéristiques) de la chambre
    bed_type = fields.Selection(
        [
            ("single", "Single"),
            ("double", "Double"),
            ("queen", "Queen"),
            ("king", "King"),
        ],
        string="Bed Type",
    )


    surface_area = fields.Float(string="Surface Area (m²)")

    flooring_type = fields.Selection(
    [
        ("tile", "Tile"),
        ("carpet", "Carpet"),
        ("wood", "Wood"),
    ],
    string="Flooring Type",
    )

    view_type = fields.Selection(
    [
        ("sea", "Sea View"),
        ("pool", "Pool View"),
        ("city", "City View"),
        ("garden", "Garden View"),
    ],
    string="View",
    )

    is_smoking_allowed = fields.Boolean(string="Smoking Allowed")
    is_pets_allowed = fields.Boolean(string="Pets Allowed")

    reservation_type_id = fields.Many2one(
    'hotel.reservation.type', 
    string="Dummy field for view",
    compute="_compute_dummy", 
    store=False
)
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
        Retourne la chronologie des réservations confirmées avec une marge avant/après
        chaque réservation (ex. pour le ménage).
        """
        self.ensure_one()

        timeline = []
        confirmed_bookings = self.env['room.booking.line'].search([
            ('room_id', '=', self.id),
            ('state', '=', 'reserved')
        ])

        for booking in confirmed_bookings:
            start_b = booking.checkin_date - buffer_duration
            end_b = booking.checkout_date + buffer_duration

            timeline.append({
                'booking_id': booking.id,
                'start': booking.checkin_date,
                'end': booking.checkout_date,
                'start_buffered': start_b,
                'end_buffered': end_b,
            })

        timeline.sort(key=lambda r: r['start_buffered'])
        return timeline

def get_reservation_slots(self, type_code):
    self.ensure_one()
    return self.reservation_slots_ids.filtered(lambda s: s.reservation_type_id.code == type_code)

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
                'booking_id': booking.id,
                'start': booking.checkin_date,
                'end': booking.checkout_date,
                'start_buffered': start_b,
                'end_buffered': end_b,
            })

        # 4. Trie la liste par date de début avec buffer
        timeline.sort(key=lambda r: r['start_buffered'])

        return timeline

    
#: Créer un nouveau modèle hotel.room.feature( à analyser la possibilté de le faire)
# tarification dynamque selon la periode , saison etc à ajouter
# concernant le late check out et early check in
# discounts sur les prix de nuitée et day use