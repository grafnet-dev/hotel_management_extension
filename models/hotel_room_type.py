from odoo import models, fields, api
from datetime import timedelta


class HotelRoomType(models.Model):
    _name = "hotel.room.type"
    _description = "Hotel Room Type"
    _order = "sequence, name"

  

    # Informations de base
    room_ids = fields.Many2one(
        "hotel.room", string="chambre", required=True, ondelete="cascade"
    )
    name = fields.Char(string="Nom du type de chambre", required=True, translate=True)
    code = fields.Char(
        string="Code",
        required=True,
        help="Code unique pour identifier le type de chambre",
    )
    sequence = fields.Integer(string="Séquence", default=10)
    active = fields.Boolean(string="Actif", default=True)
    description = fields.Text(string="Description", translate=True)
    capacity = fields.Integer(string="capacité")
    is_flexible = fields.Boolean(
        related="reservation_type_ids.is_flexible",
        string="Heures flexibles",
        default=False,
    )
    code = fields.Selection(
        related="reservation_type_ids.code", string="Code", readonly=True
    )

    # Images
    image = fields.Binary(string="Image principale", attachment=True)
    room_image_ids = fields.One2many(
        "hotel.room.type.image", "room_type_id", string="Galerie d'images"
    )

    # Caractéristiques physiques
    bed_type = fields.Selection(
        [
            ("single", "Single"),
            ("double", "Double"),
            ("queen", "Queen"),
            ("king", "King"),
        ],
        string="Type de lit",
        required=True,
    )

    surface_area = fields.Float(string="Superficie (m²)")
    max_occupancy = fields.Integer(string="Capacité maximale", default=2)

    flooring_type = fields.Selection(
        [
            ("tile", "Carrelage"),
            ("carpet", "Moquette"),
            ("wood", "Parquet"),
            ("laminate", "Stratifié"),
        ],
        string="Type de sol",
    )

    view_type = fields.Selection(
        [
            ("sea", "Vue mer"),
            ("pool", "Vue piscine"),
            ("city", "Vue ville"),
            ("garden", "Vue jardin"),
            ("mountain", "Vue montagne"),
            ("courtyard", "Vue cour"),
        ],
        string="Type de vue",
    )

    # Politiques
    is_smoking_allowed = fields.Boolean(string="Fumeur autorisé")
    is_pets_allowed = fields.Boolean(string="Animaux autorisés")

    # Types de réservation acceptés
    reservation_type_ids = fields.Many2many(
        "hotel.reservation.type",
        "hotel_room_type_reservation_type_rel",
        "room_type_id",
        "reservation_type_id",
        string="Types de réservation acceptés",
        help="Types de réservation que ce type de chambre peut accepter",
    )

    # Créneaux personnalisés
    reservation_slots_ids = fields.One2many(
        "hotel.room.reservation.slot", "room_type_id", string="Créneaux personnalisés"
    )

    # Limites horaires
    early_checkin_hour_limit = fields.Float(
        string="Limite Early Check-in",
        default=6.0,
        help="En dessous de cette heure, l'early check-in est facturé comme une nuit supplémentaire.",
    )

    late_checkout_hour_limit = fields.Float(
        string="Limite Late Check-out",
        default=18.0,
        help="Au-dessus de cette heure, le late check-out est facturé comme une nuit supplémentaire.",
    )

    policy_ids = fields.One2many(
        "hotel.eclc.policy", "room_type_id", string="Politiques Early/Late"
    )

    # Tarification
    room_pricing_ids = fields.One2many(
        "hotel.room.pricing", "room_type_id", string="Tarifications"
    )
    base_price = fields.Float(
        string="Prix de base / nuit",
        required=True,
        default=0.0,
        help="Prix standard de la chambre par nuit. Utilisé comme base pour les pourcentages.",
    )

    # Chambres de ce type
    room_ids = fields.One2many("hotel.room", "room_type_id", string="Chambres")
    room_count = fields.Integer(
        string="Nombre de chambres", compute="_compute_room_count"
    )

    # Équipements et services
    amenity_ids = fields.Many2many(
        "hotel.amenity",
        "hotel_room_type_amenity_rel",
        "room_type_id",
        "amenity_id",
        string="Équipements",
    )
    _sql_constraints = [
        (
            "code_unique",
            "unique(code)",
            "Le code du type de chambre doit être unique !",
        ),
    ]

    @api.depends("room_ids")
    def _compute_room_count(self):
        for record in self:
            record.room_count = len(record.room_ids)

    @api.model
    def create(self, vals):
        if "code" in vals:
            vals["code"] = vals["code"].upper()
        return super(HotelRoomType, self).create(vals)

    def write(self, vals):
        if "code" in vals:
            vals["code"] = vals["code"].upper()
        return super(HotelRoomType, self).write(vals)

    _sql_constraints = [
        (
            "code_unique",
            "unique(code)",
            "Le code du type de chambre doit être unique !",
        ),
    ]

    def get_checkin_checkout_time(self, type_code=None):
        """
        Retourne les horaires à appliquer selon le type de réservation demandé.
        Si non précisé, retourne les valeurs par défaut.
        """
        self.ensure_one()

        if type_code:
            reservation_type = self.env["hotel.reservation.type"].search(
                [("code", "=", type_code)], limit=1
            )
            if reservation_type and reservation_type in self.reservation_type_ids:
                return {
                    "checkin": reservation_type.checkin_time or 14.0,  # 14h par défaut
                    "checkout": reservation_type.checkout_time
                    or 12.0,  # 12h par défaut
                }

        return {
            "checkin": 14.0,  # 14h par défaut
            "checkout": 12.0,  # 12h par défaut
        }

    def get_reservation_slots(self, type_code):
        """
        Retourne les créneaux de réservation pour un type de réservation donné.
        """
        self.ensure_one()
        return self.reservation_slots_ids.filtered(
            lambda s: s.reservation_type_id.code == type_code
        )

    def get_available_rooms(self, checkin_date, checkout_date):
        """
        Retourne les chambres disponibles de ce type pour les dates données.
        """
        self.ensure_one()

        # Récupère toutes les chambres de ce type
        all_rooms = self.room_ids.filtered(lambda r: not r.is_in_maintenance)

        # Filtre les chambres occupées
        occupied_rooms = (
            self.env["room.booking.line"]
            .search(
                [
                    ("room_id", "in", all_rooms.ids),
                    ("state", "=", "reserved"),
                    ("checkin_date", "<", checkout_date),
                    ("checkout_date", ">", checkin_date),
                ]
            )
            .mapped("room_id")
        )

        return all_rooms - occupied_rooms
