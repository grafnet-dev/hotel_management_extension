from odoo import models, fields, api
from datetime import timedelta
from odoo.tools.translate import _
from odoo.exceptions import UserError
from datetime import datetime, timedelta



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
def check_availability(self, checkin_date, checkout_date, reservation_type_code=False, room_qty=1):
        """
        Vérifie la disponibilité de la chambre pour une période donnée
        selon le type de réservation spécifié.
        
        :param checkin_date: datetime - Date/heure de check-in demandée
        :param checkout_date: datetime - Date/heure de check-out demandée
        :param reservation_type_code: str - Code du type de réservation ('classic', 'dayuse', 'flexible')
        :param room_qty: int - Quantité de chambres nécessaires (par défaut 1)
        :return: dict - {
            'available': bool,
            'message': str,
            'suggested_alternatives': list[dict],
            'price': float,
            'currency': str
        }
        """
        self.ensure_one()

        if not isinstance(checkin_date, datetime) or not isinstance(checkout_date, datetime):
            raise UserError(_("Les dates doivent être des objets datetime valides"))
            
        if checkout_date <= checkin_date:
            raise UserError(_("La date de check-out doit être postérieure au check-in"))

        # 2. Vérification maintenance
        if self.is_in_maintenance:
            return {
                'available': False,
                'message': _("Cette chambre est en maintenance jusqu'au %s") % self.next_maintenance_date,
                'suggested_alternatives': self._find_alternative_rooms(checkin_date, checkout_date, reservation_type_code),
                'price': 0.0,
                'currency': self._get_currency()
            }

        # 3. Vérification type de réservation
        reservation_type = False
        if reservation_type_code:
            reservation_type = self.env['hotel.reservation.type'].search([('code', '=', reservation_type_code)], limit=1)
            if not reservation_type or reservation_type not in self.reservation_type_ids:
                return {
                    'available': False,
                    'message': _("Ce type de réservation n'est pas disponible pour cette chambre"),
                    'suggested_alternatives': [],
                    'price': 0.0,
                    'currency': self._get_currency()
                }

        # 4. Récupération des créneaux réservés avec buffer
        timeline = self.get_timeline_with_buffer()
        
        # 5. Vérification des conflits
        for slot in timeline:
            if (checkin_date < slot['end_buffered'] and checkout_date > slot['start_buffered']):
                return {
                    'available': False,
                    'message': _("La chambre n'est pas disponible du %s au %s") % (
                        slot['start'].strftime('%d/%m/%Y %H:%M'),
                        slot['end'].strftime('%d/%m/%Y %H:%M')
                    ),
                    'suggested_alternatives': self._find_alternative_rooms(checkin_date, checkout_date, reservation_type_code),
                    'price': 0.0,
                    'currency': self._get_currency()
                }

        # 6. Calcul du prix
        price = self._calculate_price(checkin_date, checkout_date, reservation_type_code)
        
        return {
            'available': True,
            'message': _("Disponible"),
            'suggested_alternatives': [],
            'price': price,
            'currency': self._get_currency()
        }

def _find_alternative_rooms(self, checkin_date, checkout_date, reservation_type_code=False):
    
    """Trouve des chambres alternatives disponibles"""
    domain = [
        ('id', '!=', self.id),
        ('is_in_maintenance', '=', False)
    ]
    
    if reservation_type_code:
        domain.append(('reservation_type_ids.code', '=', reservation_type_code))
    
    alternatives = self.search(domain).filtered(
        lambda r: r.check_availability(checkin_date, checkout_date, reservation_type_code)['available']
    )  
    return [{
    'id': room.id,
    'name': room.name,
    'price': room.get_price(checkin_date, checkout_date, reservation_type_code),
    'image': room.image_1920,
    'bed_type': room.bed_type
}  for room in alternatives[:5]] 

def _calculate_price(self, checkin_date, checkout_date, reservation_type_code=False,room_qty=1):
    """
    Calcule le prix total pour la période donnée selon le type de réservation.
    :param checkin_date: datetime - Date/heure de check-in
    :param checkout_date: datetime - Date/heure de check-out
    :param reservation_type_code: str - Code du type de réservation ('classic', 'dayuse', 'flexible')
    :return: float - Prix total
    """
    self.ensure_one()
    
    if not reservation_type_code:
        reservation_type_code = 'classic'  

    # Récupère les horaires de check-in et check-out selon le type
    times = self.get_checkin_checkout_time(reservation_type_code)
    
    # Calcule la durée en jours
    duration_days = (checkout_date - checkin_date).days
    
    if duration_days <= 0:
        return 0.0  # Pas de prix si pas de durée valide

    if reservation_type_code == 'dayuse':
        return self.day_use_price * room_qty

    elif reservation_type_code == 'flexible':
        return self.hourly_rate * (duration_days * 24)  # Tarif horaire pour flexible

    else:  # Type classique
        return self.price_per_night * duration_days
# TODO: 

 



    
#: Créer un nouveau modèle hotel.room.feature( à analyser la possibilté de le faire)
# tarification dynamque selon la periode , saison etc à ajouter
# concernant le late check out et early check in
# discounts sur les prix de nuitée et day use