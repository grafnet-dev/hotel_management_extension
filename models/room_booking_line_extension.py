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
    
    # Gestion du early check-in et late check-out
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
    
    # ✅ NOUVEAU: Distinguer flexible manuel vs automatique
    is_manual_flexible = fields.Boolean(
        "Flexible sélectionné manuellement",
        help="True si l'utilisateur a directement sélectionné le type flexible, False si requalification automatique"
    )

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
        # ✅ ÉTAPE 1: Détecter si c'est une sélection manuelle du type flexible
        if (self.reservation_type_id and self.reservation_type_id.is_flexible and 
            not self.was_requalified_flexible):
            # L'utilisateur a directement sélectionné "flexible" → mode manuel
            self.is_manual_flexible = True
            self.checkin_date = False
            self.checkout_date = False
            # Ne pas remplir automatiquement, laisser l'user saisir
            return
        elif self.reservation_type_id and not self.reservation_type_id.is_flexible:
            # Type non-flexible sélectionné → réinitialiser le flag manuel
            self.is_manual_flexible = False

        self.checkin_date = False
        self.checkout_date = False

        if not self.reservation_type_id or not self.room_id or not self.booking_date:
            return

        if self.reservation_type_id.is_flexible and not self.is_manual_flexible:
            # Flexible automatique (requalification) → ne pas remplir ici
            # Les dates seront calculées dans recalculate_checkin_checkout_dates()
            return

        # Cherche un slot défini pour cette chambre et ce type
        slot = self.env["hotel.room.reservation.slot"].search(
            [
                ("room_id", "=", self.room_id.id),
                ("reservation_type_id", "=", self.reservation_type_id.id),
            ],
            limit=1,
        )

        if not slot:
            raise ValidationError(_("Aucun créneau (slot) n'est défini pour la chambre sélectionnée et le type de réservation. Veuillez configurer les horaires dans 'hotel.room.reservation.slot'."))

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
            
        except Exception as e:
            raise ValidationError(_("Erreur lors du calcul des horaires : %s") % str(e))

    # ✅ CORRECTION 1: Une seule méthode onchange qui gère tout
    @api.onchange('early_checkin_requested', 'early_checkin_hour', 'late_checkout_requested', 'late_checkout_hour')
    def _onchange_check_flex_and_night(self):
        """
        Méthode unique qui gère :
        1. La remise à zéro des heures quand les cases sont décochées
        2. La requalification en flexible si nécessaire
        3. Le retour au type original
        4. Le recalcul des horaires
        """
        for rec in self:
            # ✅ ÉTAPE 1: Remettre à zéro les heures si les cases sont décochées
            if not rec.early_checkin_requested:
                rec.early_checkin_hour = None
            if not rec.late_checkout_requested:
                rec.late_checkout_hour = None
            
            # ✅ ÉTAPE 2: Logique de requalification
            rec._auto_check_qualification()
            #✅ ÉTAPE 3: Calcul du prix
            rec.compute_dynamic_price_unit()

    def _auto_check_qualification(self):
        """
        Logique de requalification et détection de nuit supplémentaire
        """
        for rec in self:
            if not rec.room_id:
                continue

            # Réinitialise les champs d'état
            rec.was_requalified_flexible = False
            rec.extra_night_required = False
            rec.requalification_reason = False

            # Récupère les heures limites depuis la configuration de la chambre
            early_limit = rec.room_id.early_checkin_hour_limit or 6.0
            late_limit = rec.room_id.late_checkout_hour_limit or 18.0

            reasons = []

            # Cas 1 : Early check-in
            if rec.early_checkin_requested and rec.early_checkin_hour not in [None, 0.0]:
                if rec.early_checkin_hour < early_limit:
                    rec.extra_night_required = True
                    reasons.append(f"Early Check-in à {rec.early_checkin_hour}h < limite {early_limit}h")
                else:
                    rec.was_requalified_flexible = True
                    reasons.append(f"Early Check-in demandé à {rec.early_checkin_hour}h")

            # Cas 2 : Late check-out
            if rec.late_checkout_requested and rec.late_checkout_hour not in [None, 0.0]:
                if rec.late_checkout_hour > late_limit:
                    rec.extra_night_required = True
                    reasons.append(f"Late Check-out à {rec.late_checkout_hour}h > limite {late_limit}h")
                else:
                    rec.was_requalified_flexible = True
                    reasons.append(f"Late Check-out demandé à {rec.late_checkout_hour}h")

            # ✅ CORRECTION 2: Gestion du retour au type original
            if not rec.early_checkin_requested and not rec.late_checkout_requested:
                # Aucune demande early/late active → revenir au type original
                if rec.original_reservation_type_id:
                    rec.reservation_type_id = rec.original_reservation_type_id
                    rec.original_reservation_type_id = False
                    rec.was_requalified_flexible = False
                    rec.requalification_reason = False
                    rec.is_manual_flexible = False  # ✅ Réinitialiser le flag manuel
            else:
                # Il y a des demandes early/late → basculer en flexible si nécessaire
                if reasons:
                    rec.requalification_reason = " | ".join(reasons)

                    if rec.reservation_type_id and not rec.reservation_type_id.is_flexible:
                        # Mémoriser le type original si pas encore fait
                        if not rec.original_reservation_type_id:
                            rec.original_reservation_type_id = rec.reservation_type_id
                        
                        # Chercher et assigner le type flexible
                        flexible_type = self.env['hotel.reservation.type'].search([('is_flexible', '=', True)], limit=1)
                        if flexible_type:
                            rec.reservation_type_id = flexible_type
                            rec.was_requalified_flexible = True
                            rec.is_manual_flexible = False  # ✅ Flexible automatique, pas manuel

            # ✅ ÉTAPE 3: Recalcul des horaires après tous les changements
            rec.recalculate_checkin_checkout_dates()

    def recalculate_checkin_checkout_dates(self):
        """
        Recalcule les champs checkin_date et checkout_date
        en tenant compte des demandes early/late et des heures personnalisées.
        """
        for rec in self:
            if not rec.booking_date or not rec.room_id or not rec.reservation_type_id:
                continue

            # ✅ CORRECTION MAJEURE: Ne pas toucher aux dates si flexible manuel
            if rec.reservation_type_id.is_flexible and rec.is_manual_flexible:
                # L'utilisateur a sélectionné flexible manuellement
                # → Il doit saisir les dates lui-même, on ne calcule rien
                return

            try:
                # ✅ Pour les flexibles automatiques (requalification), on calcule
                if rec.reservation_type_id.is_flexible and not rec.is_manual_flexible:
                    # Flexible automatique : on cherche le slot du type original
                    slot = None
                    if rec.original_reservation_type_id:
                        slot = rec.env["hotel.room.reservation.slot"].search([
                            ("room_id", "=", rec.room_id.id),
                            ("reservation_type_id", "=", rec.original_reservation_type_id.id),
                        ], limit=1)
                    
                    if not slot:
                        raise ValidationError(_("Impossible de calculer les horaires pour la requalification flexible."))
                else:
                    # Type non-flexible : slot normal
                    slot = rec.env["hotel.room.reservation.slot"].search([
                        ("room_id", "=", rec.room_id.id),
                        ("reservation_type_id", "=", rec.reservation_type_id.id),
                    ], limit=1)
                    
                    if not slot:
                        raise ValidationError(_("Aucun créneau horaire défini pour cette chambre et ce type de réservation."))

                # Déterminer l'heure de check-in
                if rec.early_checkin_requested and rec.early_checkin_hour not in [None, 0.0]:
                    checkin_time = float_to_time(rec.early_checkin_hour)
                else:
                    checkin_time = float_to_time(slot.checkin_time)

                checkin_dt = datetime.combine(rec.booking_date, checkin_time)

                # Déterminer la date et l'heure de checkout
                if rec.reservation_type_id.code == "classic" and rec.booking_end_date:
                    checkout_base_date = rec.booking_end_date
                else:
                    checkout_base_date = rec.booking_date

                if rec.late_checkout_requested and rec.late_checkout_hour not in [None, 0.0]:
                    checkout_time = float_to_time(rec.late_checkout_hour)
                else:
                    checkout_time = float_to_time(slot.checkout_time)

                checkout_dt = datetime.combine(checkout_base_date, checkout_time)

                # Corriger si checkout <= checkin (pour les nuitées)
                if rec.reservation_type_id.code == "classic" and checkout_dt <= checkin_dt:
                    checkout_dt += timedelta(days=1)

                rec.checkin_date = checkin_dt
                rec.checkout_date = checkout_dt

            except Exception as e:
                raise ValidationError(_("Erreur dans le calcul des horaires personnalisés : %s") % str(e))

    # Surcharger la méthode _onchange_checkin_date
    @api.onchange("checkin_date", "checkout_date")
    def _onchange_checkin_date(self):
        """
        Validation souple des dates de check-in/check-out
        """
        if not self.checkin_date or not self.checkout_date:
            return

        if self.checkout_date < self.checkin_date:
            # Correction automatique + avertissement
            self.checkout_date = self.checkin_date + timedelta(days=1)
            return {
                'warning': {
                    'title': _("Correction automatique"),
                    'message': _("La date de départ a été ajustée car elle était avant la date d'arrivée."),
                }
            }

        # Mise à jour du nombre de jours
        diffdate = self.checkout_date - self.checkin_date
        qty = diffdate.days
        if diffdate.total_seconds() > 0:
            qty += 1
        self.uom_qty = qty

    # Warning si extra_night_required est True
    @api.onchange('extra_night_required')
    def _onchange_alert_extra_night(self):
        if self.extra_night_required:
            return {
                'warning': {
                    'title': "Attention : Nuit Supplémentaire",
                    'message': "L'horaire demandé sort des limites standards. Une nuit supplémentaire sera peut-être requise.",
                }
            }

    # ✅ CORRECTION 4: Validation cohérente pour les flexibles
    @api.constrains("reservation_type_id", "checkin_date", "checkout_date")
    def _check_dates_required(self):
        """
        Pour les réservations flexibles, on recommande la saisie manuelle mais on ne l'impose pas forcément
        """
        for rec in self:
            # On peut ajouter des validations spécifiques selon les besoins métier
            # Par exemple : empêcher la sauvegarde si checkin > checkout
            if rec.checkin_date and rec.checkout_date and rec.checkout_date < rec.checkin_date:
                raise ValidationError(_("La date de départ ne peut pas être antérieure à la date d'arrivée."))

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
    
    def compute_dynamic_price_unit(self):
        """
        Version simplifiée pour démo :
        Calcule un prix unitaire simulé selon le type de réservation et les tarifs liés à la chambre.
        """
        for rec in self:
            if not rec.room_id or not rec.reservation_type_id:
                rec.price_unit = 0.0
                continue

            # Recherche du tarif lié à la chambre et au type
            pricing = self.env['hotel.room.pricing'].search([
                ('room_id', '=', rec.room_id.id),
                ('reservation_type_id', '=', rec.reservation_type_id.id)
            ], limit=1)

            if not pricing:
                rec.price_unit = 0.0
                continue

            # Logique fictive pour la démo
            # On suppose une durée fixe de 5h et que la réservation inclut des heures de nuit
            duree = 5  # en heures
            includes_night = True

            if not pricing.is_hourly_based:
                # Prix fixe
                rec.price_unit = pricing.price or 0.0
            else:
                if pricing.price_per_block and pricing.block_duration:
                    # Tarif par bloc
                    nb_blocs = duree / pricing.block_duration
                    rec.price_unit = pricing.price_per_block * nb_blocs
                else:
                    # Tarif horaire simple
                    rec.price_unit = pricing.hourly_price * duree

                # Majoration nuit (fictive)
                if includes_night and pricing.night_extra_percent:
                    rec.price_unit *= (1 + pricing.night_extra_percent / 100.0)


    