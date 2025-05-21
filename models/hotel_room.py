from odoo import models, fields


class HotelRoom(models.Model):
    _inherit = "hotel.room"

    is_day_use = fields.Boolean(string="Disponible en Day use ")
    day_use_check_in = fields.Float(string="Day Use Check-in Time")
    day_use_check_out = fields.Float(string="Day Use Check-out Time")

    # Exemple si tu veux regrouper des images multiples
    room_image_ids = fields.One2many(
        "hotel.room.image", "room_id", string="Room Gallery"
    )
    # prix de la chambre
    price_per_night = fields.Float(string="Prix par Nuitée", digits="Product Price")
    day_use_price = fields.Float(string="Day Use Price", digits="Product Price")
    hourly_rate = fields.Float(
        string="Hourly Rate (Day Use or else )", digits="Product Price"
    )

    # Champs pour la gestion de la maintenance
    is_in_maintenance = fields.Boolean(string="Under Maintenance")
    maintenance_notes = fields.Text(string="Maintenance Notes")
    last_maintenance_date = fields.Date(string="Last Maintenance Date")
    next_maintenance_date = fields.Date(string="Next Scheduled Maintenance")
    
    # Champs pour la gestion des heures de check-in et check-out
    default_check_in_time = fields.Float(string="Default Check-In Time")
    default_check_out_time = fields.Float(string="Default Check-Out Time")

    # feature de la chambre
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
    #: Créer un nouveau modèle hotel.room.feature( à analyser la possibilté de le faire)

# tarification dynamque selon la periode , saison etc à ajouter
# concernant le late check out et early check in
# discounts sur les prix de nuitée et day use
