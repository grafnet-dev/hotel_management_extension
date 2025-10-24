from odoo import models, fields, api, _
from datetime import timedelta, datetime
from odoo.exceptions import ValidationError, UserError
import uuid


class HotelRoom(models.Model):
    _inherit = "hotel.room"
    stay_ids = fields.One2many(
        "hotel.booking.stay",
        "room_id",
        string="Séjours associés",
        help="Liste des séjours ayant utilisé cette chambre",
    )

    room_type_id = fields.Many2one(
        "hotel.room.type", string="Type de chambre", required=True, ondelete="cascade"
    )
    capacity = fields.Integer(
        related="room_type_id.capacity", string="capacité", readonly=True
    )
    bed_type = fields.Selection(
        related="room_type_id.bed_type", string="Type de lit", readonly=True
    )
    surface_area = fields.Float(
        related="room_type_id.surface_area", string="Superficie", readonly=True
    )
    max_occupancy = fields.Integer(
        related="room_type_id.max_occupancy", string="Capacité max", readonly=True
    )
    active = fields.Boolean(related="room_type_id.active", string="Actif", default=True)
    room_image_ids = fields.One2many(
        related="room_type_id.room_image_ids",
        comodel_name="hotel.room.type.image",
        string="Images du type de chambre",
        readonly=True,
    )
    room_pricing_ids = fields.One2many(
        "hotel.room.pricing",
        "room_type_id",
        string="Prix par type de chambre",
        related="room_type_id.room_pricing_ids",
    )
    reservation_type_ids = fields.Many2many(
        "hotel.reservation.type",
        "hotel_room_type_reservation_type_rel",
        "room_type_id",
        "reservation_type_id",
        related="room_type_id.reservation_type_ids",
        string="Types de réservation acceptés",
        help="Types de réservation que ce type de chambre peut accepter",
    )
    reservation_slots_ids = fields.One2many(
        "hotel.room.reservation.slot",
        "room_type_id",
        related="room_type_id.reservation_slots_ids",
        string="Créneaux personnalisés",
    )
    flooring_type = fields.Selection(
        related="room_type_id.flooring_type", string="Type de sol"
    )
    view_type = fields.Selection(related="room_type_id.view_type", string="Type de vue")
    is_smoking_allowed = fields.Boolean(
        related="room_type_id.is_smoking_allowed", string="Fumeur autorisé"
    )
    is_pets_allowed = fields.Boolean(
        related="room_type_id.is_pets_allowed", string="Animaux autorisés"
    )
    # Override the field as invisible, optional
    num_person = fields.Integer(
        string="Number of Persons", compute="_compute_fake", store=False
    )

    # booking_line_ids = flooring_type = fields.Selection([

    # Champ statut ajouté
    status = fields.Selection(
        selection_add=[
            ("available", "Disponible"),
            ("occupied", "Occupée"),
            ("cleaning", "En nettoyage"),
            ("maintenance", "En maintenance"),
            ("out_of_order", "Hors service"),
            ("reserved", "Réservée"),
        ],
        string="Statut",
        default="available",
    )
    state = fields.Selection([
    ('available', 'Disponible'),
    ('occupied', 'Occupée'),
    ('to_clean', 'À nettoyer'),
    ('cleaning', 'En nettoyage'),
], string='État de nettoyage', default='available', required=True)

    # Champ dynamique pour compter les chambres disponibles par type
    available_count = fields.Integer(
        string="Nombre de chambres disponibles",
        compute="_compute_available_count",
        store=False,
        help="Nombre de chambres disponibles pour ce type de chambre",
    )

    # champs à supprimer
    price_per_night = fields.Float(string="Prix par Nuitée", digits="Product Price")
    day_use_price = fields.Float(string="Day Use Price", digits="Product Price")
    hourly_rate = fields.Float(
        string="Hourly Rate (Day Use or else )", digits="Product Price"
    )

    # Maintenance
    is_in_maintenance = fields.Boolean(string="Under Maintenance")
    maintenance_notes = fields.Text(string="Maintenance Notes")
    last_maintenance_date = fields.Date(string="Last Maintenance Date")
    next_maintenance_date = fields.Date(string="Next Scheduled Maintenance")

    reservation_type_id = fields.Many2one(
        "hotel.reservation.type",
        string="Dummy field for view",
        compute="_compute_dummy",
        store=False,
    )

    @api.depends("room_type_id", "status")
    def _compute_available_count(self):
        """
        Calcule le nombre de chambres disponibles par type de chambre
        """
        for record in self:
            if record.room_type_id:
                # Compte les chambres du même type avec le statut 'available'
                available_rooms = self.env["hotel.room"].search_count(
                    [
                        ("room_type_id", "=", record.room_type_id.id),
                        ("status", "=", "available"),
                    ]
                )
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
            reservation_type = self.env["hotel.reservation.type"].search(
                [("code", "=", type_code)], limit=1
            )
            if reservation_type and reservation_type in self.reservation_type_ids:
                return {
                    "checkin": reservation_type.checkin_time
                    or self.default_check_in_time,
                    "checkout": reservation_type.checkout_time
                    or self.default_check_out_time,
                }

        return {
            "checkin": self.default_check_in_time,
            "checkout": self.default_check_out_time,
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
        confirmed_bookings = self.env["room.booking.line"].search(
            [
                ("room_id", "=", self.id),  # La chambre concernée
                ("state", "=", "reserved"),  # Seulement les réservations confirmées
            ]
        )

        # 2. Parcourt chaque réservation
        for booking in confirmed_bookings:
            # Calcule la date de début avec buffer (1h avant le check-in)
            start_b = booking.checkin_date - buffer_duration
            # Calcule la date de fin avec buffer (1h après le check-out)
            end_b = booking.checkout_date + buffer_duration

            # 3. Ajoute les informations dans la timeline
            timeline.append(
                {
                    "start": booking.checkin_date,
                    "end": booking.checkout_date,
                    "start_buffered": start_b,
                    "end_buffered": end_b,
                }
            )

        # 4. Trie la liste par date de début avec buffer
        timeline.sort(key=lambda r: r["start_buffered"])

        return timeline

    def get_reservation_slots(self, type_code):
        self.ensure_one()
        return self.reservation_slots_ids.filtered(
            lambda s: s.reservation_type_id.code == type_code
        )

    @api.model
    def get_available_rooms_by_type(self, room_type_id):
        """
        Méthode utilitaire pour obtenir toutes les chambres disponibles d'un type donné
        """
        return self.search(
            [("room_type_id", "=", room_type_id), ("status", "=", "available")]
        )

    @api.model
    def get_availability_summary(self):
        """
        Retourne un résumé de la disponibilité par type de chambre
        """
        room_types = self.env["hotel.room.type"].search([])
        summary = []

        for room_type in room_types:
            available_count = self.search_count(
                [("room_type_id", "=", room_type.id), ("status", "=", "available")]
            )
            total_count = self.search_count([("room_type_id", "=", room_type.id)])

            summary.append(
                {
                    "room_type": room_type.name,
                    "available": available_count,
                    "total": total_count,
                    "occupancy_rate": (
                        ((total_count - available_count) / total_count * 100)
                        if total_count > 0
                        else 0
                    ),
                }
            )

        return summary

    # Action methods - properly indented as class methods
    def action_set_available(self):
        self.status = "available"

    def action_set_occupied(self):
        self.status = "occupied"

    def action_set_cleaning(self):
        self.status = "cleaning"

    def action_set_maintenance(self):
        self.status = "maintenance"

    def action_view_room_type_pricing(self):
        return {
            "name": "Tarification du Type",
            "type": "ir.actions.act_window",
            "res_model": "hotel.room.type",
            "res_id": self.room_type_id.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_view_room_type_reservation_types(self):
        return {
            "name": "Types de Réservation",
            "type": "ir.actions.act_window",
            "res_model": "hotel.room.type",
            "res_id": self.room_type_id.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_view_room_type_details(self):
        return {
            "name": "Détails du Type de Chambre",
            "type": "ir.actions.act_window",
            "res_model": "hotel.room.type",
            "res_id": self.room_type_id.id,
            "view_mode": "form",
            "target": "new",
        }

    def _compute_fake(self):
        for rec in self:
            rec.num_person = 0  # ou rien, selon le besoin

    @api.model
    def get_room_activities(self, room_id, start_date, end_date):
        """
        Retourne toutes les activités d'une chambre (séjours, nettoyages, etc.)
        entre deux dates données, avec gestion d'erreurs et format uniforme.

        :param room_type_id: int → ID du type de chambre
        :param start_date: str (YYYY-MM-DD)
        :param end_date: str (YYYY-MM-DD)
        :return: dict {success: bool, message: str, data: list}
        """
        try:
            # === Validation des entrées ===
            if not room_id:
                raise ValidationError(_("Aucun type de chambre spécifié."))

            if not start_date or not end_date:
                raise ValidationError(
                    _("Les dates de début et de fin sont obligatoires.")
                )

            try:
                start_dt = datetime.strptime(start_date, "%Y-%m-%d")
                end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            except ValueError:
                raise ValidationError(
                    _("Le format de date est invalide. Utilisez YYYY-MM-DD.")
                )

            if end_dt < start_dt:
                raise ValidationError(
                    _("La date de fin doit être postérieure à la date de début.")
                )

            # === Vérification du type de chambre ===
            room = self.browse(room_id)
            if not room.exists():
                raise ValidationError(_("La chambre spécifiée n'existe pas."))

            activities = []

            # === Récupération des séjours ===
            stays = self.env["hotel.booking.stay"].search(
                [
                    ("room_id", "=", room_id),
                    ("state", "in", ["pending", "ongoing"]),
                    "|",
                    "&",
                    ("planned_checkin_date", ">=", start_dt),
                    ("planned_checkin_date", "<=", end_dt),
                    "&",
                    ("planned_checkout_date", ">=", start_dt),
                    ("planned_checkout_date", "<=", end_dt),
                ]
            )

            for s in stays:
                type_code = "stay_ongoing" if s.state == "ongoing" else "upcoming_stay"
                label = "Séjour en cours" if s.state == "ongoing" else "Séjour à venir"

                activities.append(
                    {
                        "id": s.id,
                        "room_id": s.room_id.id,
                        "room_name": s.room_id.name,
                        "type": type_code,
                        "label": label,
                        "start": fields.Datetime.to_string(s.planned_checkin_date),
                        "end": fields.Datetime.to_string(s.planned_checkout_date),
                        "guest_names": s.occupant_names or "",
                        "booking_ref": s.booking_id.name if s.booking_id else "",
                    }
                )
                
                """Crée une activité de nettoyage simulée de 30 min après un séjour."""
                cleaning_duration = timedelta(minutes=30)
                cleaning_start = s.planned_checkout_date
                cleaning_end = s.planned_checkout_date + cleaning_duration
                                
                activities.append({
                    "id": f"sim_clean_{s.id}",
                    "room_id": s.room_id.id,
                    "room_name": s.room_id.name,
                    "type": "cleaning",
                    "label": "Nettoyage prévu ",
                    "start": fields.Datetime.to_string(cleaning_start),
                    "end": fields.Datetime.to_string(cleaning_end),
                })

            # ===  Tri chronologique ===
            activities.sort(key=lambda x: x["start"] or "")
            
            # === 5️⃣ Détection des créneaux libres ===
            free_slots = []

            for i in range(len(activities) - 1):
                current_end = fields.Datetime.from_string(activities[i]["end"])
                next_start = fields.Datetime.from_string(activities[i + 1]["start"])

                # Si un trou existe entre deux activités
                if current_end < next_start:
                    free_slots.append({
                        "id": f"free_{room_id}_{uuid.uuid4().hex}",
                        "room_id": room.id,
                        "room_name": room.name,
                        "type": "free_slot",
                        "label": "Créneau non exploitable",
                        "start": fields.Datetime.to_string(current_end),
                        "end": fields.Datetime.to_string(next_start),
                    })

            # === 6️⃣ Slots avant et après l’intervalle demandé ===
            if activities:
                first_start = fields.Datetime.from_string(activities[0]["start"])
                last_end = fields.Datetime.from_string(activities[-1]["end"])

                # Avant la première activité
                if first_start > start_dt:
                    free_slots.append({
                        "id": f"free_{room_id}_{uuid.uuid4().hex}",
                        "room_id": room.id,
                        "room_name": room.name,
                        "type": "free_slot",
                        "label": "Disponible",
                        "start": fields.Datetime.to_string(start_dt),
                        "end": activities[0]["start"],
                    })

                # Après la dernière activité
                if last_end < end_dt:
                    free_slots.append({
                        "id": f"free_{room_id}_{uuid.uuid4().hex}",
                        "room_id": room.id,
                        "room_name": room.name,
                        "type": "free_slot",
                        "label": "Disponible",
                        "start": activities[-1]["end"],
                        "end": fields.Datetime.to_string(end_dt),
                    })
            else:
                # Aucune activité → toute la période est libre
                free_slots.append({
                    "id": f"free_{room_id}_{uuid.uuid4().hex}",
                    "room_id": room.id,
                    "room_name": room.name,
                    "type": "free_slot",
                    "label": "Disponible (aucune réservation)",
                    "start": fields.Datetime.to_string(start_dt),
                    "end": fields.Datetime.to_string(end_dt),
                })

            # === 7️⃣ Fusion des activités ===
            activities.extend(free_slots)
            activities.sort(key=lambda x: x["start"] or "")
            
            # ===  Retour structuré ===
            message = (
                _("Aucune activité trouvée pour ce type de chambre.")
                if not activities
                else _("Activités récupérées avec succès.")
            )

            return {
                "success": True,
                "message": message,
                "data": activities,
            }

        # === 7️⃣ Gestion d'erreurs ===
        except (ValidationError, UserError) as e:
            return {
                "success": False,
                "message": str(e),
                "data": [],
            }
        except Exception as e:
            return {
                "success": False,
                "message": _("Erreur interne : %s") % str(e),
                "data": [],
            }


#: Créer un nouveau modèle hotel.room.feature( à analyser la possibilté de le faire)
# tarification dynamque selon la periode , saison etc à ajouter
# concernant le late check out et early check in
# discounts sur les prix de nuitée et day use
