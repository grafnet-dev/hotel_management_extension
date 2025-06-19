from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta, time

def float_to_time(float_hour):
    hours = int(float_hour)
    minutes = int(round((float_hour - hours) * 60))
    return time(hour=hours, minute=minutes)

class RoomBookingLine(models.Model):
    _inherit = "room.booking.line"

    reservation_type_id = fields.Many2one(
        "hotel.reservation.type",
        string="Type de réservation",
        help="Type de réservation sélectionné pour cette chambre",
    )

    booking_date = fields.Date(
        string="Date de réservation",
        help="Date utilisée pour calculer automatiquement les horaires de check-in et check-out",
    )
    
    booking_end_date = fields.Date(
    string="Date de fin de réservation",
    help="Date de fin utilisée pour calculer la date de départ pour les réservations sur plusieurs nuitées",
    )
    
    #Gestion du early check-in et late check-out
    early_checkin_requested = fields.Boolean("Early Check-in demandé")
    late_checkout_requested = fields.Boolean("Late Check-out demandé")
    early_checkin_hour = fields.Float("Heure Early Check-in", help="Ex: 10.5 = 10h30")
    early_checkin_time_display = fields.Datetime(
    string="Heure Early Check-in (affichée)",
    compute="_compute_eci_display",
    inverse="_inverse_eci_display",
    store=False,
    )

    late_checkout_hour = fields.Float("Heure Late Check-out")
    late_checkout_time_display = fields.Datetime(
    string="Heure Late Check-out (affichée)",
    compute="_compute_lco_display",
    inverse="_inverse_lco_display",
    store=False,
    )
    original_reservation_type_id = fields.Many2one(
    "hotel.reservation.type",
    string="Type d'origine",
    help="Type de réservation sélectionné initialement avant requalification flexible.",
    readonly=True,
    copy=False
    )
    # Stocker le résultat de la requalification automatique
    was_requalified_flexible = fields.Boolean("Requalifié en Flexible")
    requalification_reason = fields.Char("Motif de requalification")
    extra_night_required = fields.Boolean(string="Nuit supplémentaire requise", default=False)


    # filtrer les types en fonction de la chambre sélectionnée room_id
    @api.onchange("room_id")
    def _onchange_room_id(self):
        if self.room_id:
            return {
                "domain": {
                    "reservation_type_id": [
                        ("id", "in", self.room_id.reservation_type_ids.ids)
                    ]
                }
            }
        else:
            return {"domain": {"reservation_type_id": []}}
    
    # Automatisme principal : remplissage des dates selon le type de reservation
    @api.onchange("reservation_type_id", "booking_date", "booking_end_date", "room_id")
    def _onchange_auto_fill_dates(self):
        self.checkin_date = False
        self.checkout_date = False

        if not self.reservation_type_id or not self.room_id or not self.booking_date:
            return

        if self.reservation_type_id.is_flexible:
            # Ne rien remplir automatiquement
            return # Pas de calcul auto pour les flexibles


        # Cherche un slot défini pour cette chambre et ce type
        slot = self.env["hotel.room.reservation.slot"].search(
            [
                ("room_id", "=", self.room_id.id),
                ("reservation_type_id", "=", self.reservation_type_id.id),
            ],
            limit=1,
        )

        if not slot:
            raise ValidationError(_("Aucun créneau (slot) n’est défini pour la chambre sélectionnée et le type de réservation. Veuillez configurer les horaires dans 'hotel.room.reservation.slot'."))


        try:
            
            checkin_time = float_to_time(slot.checkin_time)
            checkout_time = float_to_time(slot.checkout_time)
            # Construit le check-in
            checkin_dt = datetime.combine(self.booking_date, checkin_time)

            if self.reservation_type_id.code == "classic" and self.booking_end_date:
                # Pour plusieurs nuitées, checkout = date de fin à l'heure de fin
                checkout_dt = datetime.combine(self.booking_end_date, checkout_time)
            else:
                # Par défaut, checkout le même jour (day use)
                checkout_dt = datetime.combine(self.booking_date, checkout_time)

                # Pour les nuitées avec checkout avant checkin, on décale d'un jour
                if self.reservation_type_id.code == "classic" and checkout_dt <= checkin_dt:
                    checkout_dt += timedelta(days=1)

            self.checkin_date = checkin_dt
            self.checkout_date = checkout_dt
             # En cas de problème de conversion (rare mais prudent)
        except Exception as e:
            raise ValidationError(_("Erreur lors du calcul des horaires : %s") % str(e))

    # Méthode pour requalifier en flexible si nécessaire et transformation en nuitée si nécessaire
    # Cette méthode est déclenchée automatiquement lorsque l’un des champs listés est modifié dans le formulaire
    @api.onchange('early_checkin_requested', 'early_checkin_hour', 'late_checkout_requested', 'late_checkout_hour')
    def _onchange_check_flex_and_night(self):
        for rec in self:
            # Appelle la méthode de vérification complète pour chaque ligne
            rec._auto_check_qualification()
    # Cette méthode contient la logique de requalification + détection de nuit supplémentaire
    def _auto_check_qualification(self):
        for rec in self:
            if not rec.room_id:
                continue  # S’il n’y a pas de chambre liée, on ne peut pas faire les vérifications

            # Réinitialise les champs d’état
            rec.was_requalified_flexible = False
            rec.extra_night_required = False
            rec.requalification_reason = False

            # Récupère les heures limites depuis la configuration de la chambre
            early_limit = rec.room_id.early_checkin_hour_limit or 6.0
            late_limit = rec.room_id.late_checkout_hour_limit or 18.0

            reasons = []  # On accumulera ici les raisons de requalification

            # Cas 1 : Early check-in
            if rec.early_checkin_requested and rec.early_checkin_hour not in [None, 0.0]:
                if rec.early_checkin_hour < early_limit:
                    # Si l’heure demandée est en dessous de la limite → une nuit supplémentaire est requise
                    rec.extra_night_required = True
                    reasons.append(f"Early Check-in à {rec.early_checkin_hour}h < limite {early_limit}h")
                else:
                    # Sinon, on requalifie en "Flexible" (sans nuit supplémentaire)
                    rec.was_requalified_flexible = True
                    reasons.append(f"Early Check-in demandé à {rec.early_checkin_hour}h")

            # Cas 2 : Late check-out
            if rec.late_checkout_requested and rec.late_checkout_hour not in [None, 0.0]:
                if rec.late_checkout_hour > late_limit:
                    # Heure demandée supérieure à la limite → nuit supplémentaire
                    rec.extra_night_required = True
                    reasons.append(f"Late Check-out à {rec.late_checkout_hour}h > limite {late_limit}h")
                else:
                    # Sinon, on accepte en tant que réservation flexible
                    rec.was_requalified_flexible = True
                    reasons.append(f"Late Check-out demandé à {rec.late_checkout_hour}h")

            # Si des raisons ont été détectées, on met à jour la justification textuelle
            if reasons:
                rec.requalification_reason = " | ".join(reasons)

                # Si le type de réservation actuel n'est pas déjà "Flexible", on le change
                if rec.reservation_type_id and not rec.reservation_type_id.is_flexible:
                    # On cherche un type de réservation ayant le flag `is_flexible`
                    flexible_type = self.env['hotel.reservation.type'].search([('is_flexible', '=', True)], limit=1)
                    if flexible_type:
                        # Mémoriser le type original si pas encore enregistré
                        if not rec.original_reservation_type_id:
                            rec.original_reservation_type_id = rec.reservation_type_id
                        rec.reservation_type_id = flexible_type
                        rec.was_requalified_flexible = True
                
            # Revenir au type original si aucune demande early/late n’est active
            if not rec.early_checkin_requested and not rec.late_checkout_requested:
                if rec.original_reservation_type_id:
                    rec.reservation_type_id = rec.original_reservation_type_id
                    rec.original_reservation_type_id = False
                    rec.was_requalified_flexible = False
                    rec.requalification_reason = False
            # Mise à jour finale des horaires
            rec.recalculate_checkin_checkout_dates()
    

    #methode pour recalculer les horaires de check-in et check-out après modification des champs early_checkin_hour et late_checkout_hour
    def recalculate_checkin_checkout_dates(self):
        """
        Recalcule les champs checkin_date et checkout_date
        en tenant compte des demandes early/late et des heures personnalisées.
        """
        for rec in self:
            if not rec.booking_date or not rec.room_id or not rec.reservation_type_id:
                continue

            try:
                # Déterminer l’heure de check-in
                if rec.early_checkin_requested and rec.early_checkin_hour not in [None, 0.0]:
                    checkin_time = float_to_time(rec.early_checkin_hour)
                else:
                    # Utilise le slot par défaut
                    slot = rec.env["hotel.room.reservation.slot"].search([
                        ("room_id", "=", rec.room_id.id),
                        ("reservation_type_id", "=", rec.reservation_type_id.id),
                    ], limit=1)
                    if not slot:
                        # Pas de slot requis si type flexible
                        if rec.reservation_type_id.is_flexible:
                            rec.checkin_date = None
                            rec.checkout_date = None
                            continue
                        raise ValidationError(_("Aucun créneau horaire défini pour cette chambre et ce type de réservation."))
                    checkin_time = float_to_time(slot.checkin_time)

                checkin_dt = datetime.combine(rec.booking_date, checkin_time)

                # Déterminer la date et l’heure de checkout
                if rec.reservation_type_id and rec.reservation_type_id.code == "classic" and rec.booking_end_date:
                    checkout_base_date = rec.booking_end_date
                else:
                    checkout_base_date = rec.booking_date

                if rec.late_checkout_requested and rec.late_checkout_hour not in [None, 0.0]:
                    checkout_time = float_to_time(rec.late_checkout_hour)
                else:
                    # Utilise le slot par défaut
                    slot = rec.env["hotel.room.reservation.slot"].search([
                        ("room_id", "=", rec.room_id.id),
                        ("reservation_type_id", "=", rec.reservation_type_id.id),
                    ], limit=1)
                    if not slot:
                        if rec.reservation_type_id and rec.reservation_type_id.is_flexible:
                            rec.checkin_date = checkin_dt  # On garde le check-in s’il est défini
                            rec.checkout_date = None
                            continue
                        raise ValidationError(_("Aucun créneau horaire défini pour cette chambre et ce type de réservation."))
                    checkout_time = float_to_time(slot.checkout_time)

                checkout_dt = datetime.combine(checkout_base_date, checkout_time)

                # Corriger si checkout <= checkin (pour les nuitées)
                if rec.reservation_type_id and rec.reservation_type_id.code == "classic" and checkout_dt <= checkin_dt:
                    checkout_dt += timedelta(days=1)

                rec.checkin_date = checkin_dt
                rec.checkout_date = checkout_dt

            except Exception as e:
                raise ValidationError(_("Erreur dans le calcul des horaires personnalisés : %s") % str(e))

    # Surcharger la méthode _onchange_checkin_date
    @api.onchange("checkin_date", "checkout_date")
    def _onchange_checkin_date(self):
        """
        On remplace la logique trop stricte de base :
        - On ne vérifie que si les 2 champs sont bien remplis.
        - On ne bloque pas si l'utilisateur est en train de modifier les dates.
        """
        if not self.checkin_date or not self.checkout_date:
            return  # Laisse l'utilisateur finir de remplir sans erreur

        if self.checkout_date < self.checkin_date:
            # Correction automatique + avertissement
            self.checkout_date = self.checkin_date + timedelta(days=1)
            return {
                'warning': {
                    'title': _("Correction automatique"),
                    'message': _("La date de départ a été ajustée car elle était avant la date d'arrivée."),
                }
            }

        # Si les deux dates sont valides → mise à jour du nombre de jours (si utilisé)
        diffdate = self.checkout_date - self.checkin_date
        qty = diffdate.days
        if diffdate.total_seconds() > 0:
            qty += 1
        self.uom_qty = qty

    #forcer la remise à None des heures lorsque les cases sont décochées
    @api.onchange('early_checkin_requested')
    def _onchange_eci_requested(self):
        if not self.early_checkin_requested:
            self.early_checkin_hour = None
            self.recalculate_checkin_checkout_dates()
    @api.onchange('late_checkout_requested')
    def _onchange_lco_requested(self):
        if not self.late_checkout_requested:
            self.late_checkout_hour = None
            self.recalculate_checkin_checkout_dates() 

    #warning si extra_night_required est True
    @api.onchange('extra_night_required')
    def _onchange_alert_extra_night(self):
        if self.extra_night_required:
            return {
                'warning': {
                    'title': "Attention : Nuit Supplémentaire",
                    'message': "L'horaire demandé sort des limites standards. Une nuit supplémentaire sera peut-être requise.",
                }
            }
    # Validation (ex. dates obligatoires sauf si flexible)
    @api.constrains("reservation_type_id", "checkin_date", "checkout_date")
    def _check_dates_required(self):
        for rec in self:
            if rec.reservation_type_id and rec.reservation_type_id.is_flexible:
                if not rec.checkin_date or not rec.checkout_date:
                    raise ValidationError(
                        "Pour une réservation flexible, les dates doivent être saisies manuellement."
                    )

    @api.constrains("booking_date", "booking_end_date", "reservation_type_id")
    def _check_booking_dates_order(self):
        for rec in self:
            if (
                rec.reservation_type_id
                and rec.reservation_type_id.code == "classic"
                and rec.booking_date
                and rec.booking_end_date
                and rec.booking_end_date < rec.booking_date
            ):
                raise ValidationError(
                    _("La date de fin de réservation ne peut pas être antérieure à la date de début.")
                )

    
    
    