"""
Moteur de vérification de disponibilité des chambres d'hôtel - VERSION STRICTE
Gère l'attribution automatique et la détection de conflits de réservation
avec règles métier strictes pour les alternatives et indisponibilité partielle
"""

import logging
from datetime import datetime, timedelta
from odoo import models, api, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class HotelRoomAvailabilityEngine(models.AbstractModel):
    """
    Moteur de disponibilité pour la gestion des réservations de chambres.
    
    Responsabilités:
    - Vérifier la disponibilité des chambres pour une période donnée
    - Attribuer automatiquement une chambre disponible
    - Proposer des alternatives conformes aux règles métier
    - Gérer les buffers de nettoyage entre réservations
    - REFUSER toute réservation avec chevauchement partiel ou total
    """
    _name = 'hotel.room.availability.engine'
    _description = 'Moteur de disponibilité des chambres'

    # ==================== MÉTHODES PUBLIQUES ====================

    @api.model
    def check_availability(self, room_type_id, checkin_date, checkout_date, 
                          exclude_stay_id=None, buffer_hours=None, reservation_type_id=None):
        """
        Point d'entrée principal : vérifie la disponibilité et retourne une chambre.
        
        RÈGLE PRINCIPALE: Refus si chevauchement partiel ou total avec période réservée
        
        :param room_type_id: ID du type de chambre recherché
        :param checkin_date: datetime de début de séjour
        :param checkout_date: datetime de fin de séjour
        :param exclude_stay_id: ID du séjour à exclure (pour modification)
        :param buffer_hours: heures de marge pour le nettoyage
        :param reservation_type_id: ID du type de réservation (pour validation horaires)
        :return: dict avec status, room_id, message, alternatives
        """
        _logger.info(
            "[AVAILABILITY] Début vérification | type=%s | in=%s | out=%s",
            room_type_id, checkin_date, checkout_date
        )

        # 1- Validation des entrées
        validation_result = self._validate_inputs(
            room_type_id, checkin_date, checkout_date
        )
        if not validation_result['valid']:
            return validation_result

        # 2- Récupérer toutes les chambres du type demandé
        rooms = self._get_rooms_by_type(room_type_id)
        
        if not rooms:
            return self._build_unavailable_response(
                message=_("Aucune chambre de ce type n'existe dans le système."),
                alternatives=[],
                reason='no_rooms'
            )

        # Calculer le buffer
        buffer_duration = timedelta(hours=buffer_hours) if buffer_hours else timedelta(0)
        _logger.debug("[AVAILABILITY] Buffer appliqué : %s", buffer_duration)

        # Parcourir les chambres pour trouver une disponible
        conflict_details = []
        for room in rooms:
            is_available, conflicts = self._check_room_availability(
                room, checkin_date, checkout_date, 
                buffer_duration, exclude_stay_id
            )
            
            if is_available:
                _logger.info(
                    "[AVAILABILITY] ✅ Chambre trouvée | room_id=%s | num=%s",
                    room.id, room.name
                )
                return self._build_available_response(room)
            else:
                # Enregistrer les conflits pour analyse
                conflict_details.extend(conflicts)

        # Aucune chambre disponible : analyser les conflits et chercher alternatives
        _logger.warning(
            "[AVAILABILITY] ❌ TOUTES LES CHAMBRES OCCUPÉES | type=%s | période=%s à %s",
            room_type_id, checkin_date, checkout_date
        )
        
        # Trouver la chambre qui se libère le plus tôt
        earliest_liberation = self._find_earliest_liberation(
            rooms, checkin_date, checkout_date, buffer_duration, exclude_stay_id
        )
        
        # Générer des alternatives basées sur les libérations
        alternatives = self._generate_smart_alternatives(
            rooms, checkin_date, checkout_date, 
            buffer_duration, reservation_type_id,
            earliest_liberation
        )
        
        return self._build_unavailable_response(
            message=_("Toutes les chambres de type '%s' sont occupées du %s au %s. "
                     "Chevauchement détecté avec des réservations existantes.") % (
                self.env['hotel.room.type'].browse(room_type_id).name,
                checkin_date.strftime('%d/%m/%Y %H:%M'),
                checkout_date.strftime('%d/%m/%Y %H:%M')
            ),
            alternatives=alternatives,
            reason='overlap_conflict',
            conflict_details=conflict_details
        )


    # ==================== MÉTHODES PRIVÉES - VALIDATION ====================

   
    def _validate_inputs(self, room_type_id, checkin_date, checkout_date):
        """
        Valide les paramètres d'entrée pour la vérification de disponibilité.
        
        Vérifie:
        - Présence du type de chambre
        - Présence des dates
        - Format des dates (datetime)
        - Cohérence des dates (checkout > checkin)
        - Dates non antérieures à aujourd'hui
        
        :return: dict avec 'valid' (bool) et éventuellement 'status' et 'message'
        """
        # Validation du type de chambre
        if not room_type_id:
            return {
                'valid': False,
                'status': 'error',
                'message': _("Le type de chambre est obligatoire.")
            }
        
        # Validation de la présence des dates
        if not checkin_date or not checkout_date:
            return {
                'valid': False,
                'status': 'error',
                'message': _("Les dates de check-in et check-out sont obligatoires.")
            }
        
        # Validation du type des dates
        if not isinstance(checkin_date, datetime) or not isinstance(checkout_date, datetime):
            return {
                'valid': False,
                'status': 'error',
                'message': _("Les dates doivent être des objets datetime.")
            }
        
        # Validation de la cohérence des dates
        if checkout_date <= checkin_date:
            return {
                'valid': False,
                'status': 'error',
                'message': _("La date de départ doit être après la date d'arrivée.")
            }
        
        # Validation des dates dans le passé
        now = datetime.now()
        
        if checkin_date < now:
            return {
                'valid': False,
                'status': 'error',
                'message': _("La date d'arrivée ne peut pas être dans le passé. "
                            "Date demandée: %s, Date actuelle: %s") % (
                    checkin_date.strftime('%d/%m/%Y %H:%M'),
                    now.strftime('%d/%m/%Y %H:%M')
                )
            }
        
        if checkout_date < now:
            return {
                'valid': False,
                'status': 'error',
                'message': _("La date de départ ne peut pas être dans le passé. "
                            "Date demandée: %s, Date actuelle: %s") % (
                    checkout_date.strftime('%d/%m/%Y %H:%M'),
                    now.strftime('%d/%m/%Y %H:%M')
                )
            }
        
        # Validation optionnelle: durée minimale (ajustez selon vos besoins)
        min_duration = timedelta(hours=1)
        actual_duration = checkout_date - checkin_date
        
        if actual_duration < min_duration:
            return {
                'valid': False,
                'status': 'error',
                'message': _("La durée du séjour doit être d'au moins %d heure(s). "
                            "Durée demandée: %d minute(s)") % (
                    min_duration.total_seconds() / 3600,
                    actual_duration.total_seconds() / 60
                )
            }
        
        # Toutes les validations sont passées
        return {'valid': True}
        
    # ==================== MÉTHODES PRIVÉES - RÉCUPÉRATION DONNÉES ====================

    def _get_rooms_by_type(self, room_type_id):
        """Récupère toutes les chambres actives d'un type donné"""
        return self.env['hotel.room'].search([
            ('room_type_id', '=', room_type_id),
            ('active', '=', True),
            ('status', 'not in', ['out_of_order', 'maintenance'])
        ], order='name')

    # ==================== MÉTHODES PRIVÉES - LOGIQUE DISPONIBILITÉ ====================

    def _check_room_availability(self, room, checkin_date, checkout_date, 
                                 buffer_duration, exclude_stay_id=None):
        """
        Vérifie si une chambre est disponible pour la période demandée.
        RÈGLE: Refus en cas de chevauchement partiel ou total
        
        :return: tuple (is_available, conflicts_list)
        """
        _logger.debug(
            "[CHECK] Vérif chambre=%s | in=%s | out=%s | buffer=%s",
            room.name, checkin_date, checkout_date, buffer_duration
        )

        domain = [
            ('room_id', '=', room.id),
            ('state', 'in', ['pending', 'ongoing']),
        ]
        if exclude_stay_id:
            domain.append(('id', '!=', exclude_stay_id))
        
        existing_stays = self.env['hotel.booking.stay'].search(domain, order='actual_checkin_date')

        requested_start_buffered = checkin_date - buffer_duration
        requested_end_buffered = checkout_date + buffer_duration

        conflicts = []
        for stay in existing_stays:
            stay_start = stay.actual_checkin_date
            stay_end = stay.actual_checkout_date
            
            # ⚠️ Ignore les séjours sans dates définies
            if not stay_start or not stay_end:
                _logger.debug("[CHECK] ⚠️ Stay %s ignoré : dates incomplètes (start=%s, end=%s)", stay.id, stay_start, stay_end)
                continue


            stay_start_buffered = stay_start - buffer_duration
            stay_end_buffered = stay_end + buffer_duration

            # Vérification stricte du chevauchement (partiel ou total)
            has_overlap = self._check_overlap(
                requested_start_buffered, requested_end_buffered,
                stay_start_buffered, stay_end_buffered
            )

            if has_overlap:
                overlap_type = self._determine_overlap_type(
                    checkin_date, checkout_date,
                    stay_start, stay_end
                )
                
                _logger.debug(
                    "[CHECK] ❌ CONFLIT %s | stay_id=%s | période=%s → %s",
                    overlap_type, stay.id, stay_start, stay_end
                )
                
                conflicts.append({
                    'room_id': room.id,
                    'room_name': room.name,
                    'stay_id': stay.id,
                    'checkin': stay_start,
                    'checkout': stay_end,
                    'overlap_type': overlap_type,
                    'booking_ref': stay.booking_id.name if stay.booking_id else None
                })

        if conflicts:
            _logger.debug("[CHECK] ❌ Chambre %s INDISPONIBLE - %d conflit(s)", room.name, len(conflicts))
            return False, conflicts

        _logger.debug("[CHECK] ✅ Chambre disponible=%s", room.name)
        return True, []

    def _check_overlap(self, start1, end1, start2, end2):
        """
        Vérifie si deux périodes se chevauchent (même partiellement)
        Retourne True si les périodes se touchent ou se chevauchent
        """
        return start1 < end2 and start2 < end1

    def _determine_overlap_type(self, req_start, req_end, existing_start, existing_end):
        """
        Détermine le type de chevauchement pour mieux informer l'utilisateur
        """
        if req_start >= existing_start and req_end <= existing_end:
            return 'TOTAL_INCLUSION'  # La demande est totalement incluse dans existant
        elif req_start < existing_start and req_end > existing_end:
            return 'TOTAL_COVERAGE'   # La demande couvre totalement l'existant
        elif req_start < existing_start < req_end:
            return 'PARTIEL_FIN'      # Chevauchement sur la fin de la demande
        elif req_start < existing_end < req_end:
            return 'PARTIEL_DEBUT'    # Chevauchement sur le début de la demande
        else:
            return 'PARTIEL_AUTRE'

    # ==================== MÉTHODES PRIVÉES - ANALYSE CONFLITS ====================

    def _find_earliest_liberation(self, rooms, requested_checkin, requested_checkout, 
                                   buffer_duration, exclude_stay_id=None):
        """
        Trouve la chambre qui se libère le plus tôt après le checkin demandé.
        Utile pour proposer des alternatives intelligentes.
        
        :return: dict avec room_id, liberation_date, next_available_start
        """
        earliest = None
        
        for room in rooms:
            domain = [
                ('room_id', '=', room.id),
                ('state', 'in', ['pending', 'ongoing']),
                ('actual_checkout_date', '>', requested_checkin)
            ]
            if exclude_stay_id:
                domain.append(('id', '!=', exclude_stay_id))
            
            # Trouver les séjours qui bloquent la période demandée
            blocking_stays = self.env['hotel.booking.stay'].search(
                domain, 
                order='actual_checkout_date',
                limit=1
            )
            
            if blocking_stays:
                liberation_date = blocking_stays[0].actual_checkout_date + buffer_duration
                
                if not earliest or liberation_date < earliest['liberation_date']:
                    earliest = {
                        'room_id': room.id,
                        'room_name': room.name,
                        'liberation_date': liberation_date,
                        'blocking_stay_id': blocking_stays[0].id
                    }
        
        if earliest:
            _logger.info(
                "[EARLIEST] Chambre %s se libère le %s",
                earliest['room_name'], earliest['liberation_date']
            )
        
        return earliest

    # ==================== MÉTHODES PRIVÉES - ALTERNATIVES INTELLIGENTES ====================

    
    def _generate_smart_alternatives(self, rooms, requested_checkin, requested_checkout,
                                 buffer_duration, reservation_type_id, 
                                 earliest_liberation, max_alternatives=3):
        """
        Génère des alternatives STRICTES basées sur:
        1. Créneaux COMPLÈTEMENT libres (aucun chevauchement)
        2. Durée EXACTE ou égale à la demande initiale
        3. Créneaux horaires VALIDES uniquement
        4. Dates NON antérieures à aujourd'hui
        
        NOUVELLES RÈGLES STRICTES:
        - Ne propose que des créneaux de durée égale (tolérance 1h)
        - Vérifie que TOUT le créneau est libre (pas de chevauchement partiel)
        - Respecte OBLIGATOIREMENT les horaires autorisés
        
        :return: liste limitée à max_alternatives (3 par défaut)
        """
        _logger.info("[ALTERNATIVES] Génération de %d alternatives STRICTES", max_alternatives)
        
        now = datetime.now()
        requested_duration = requested_checkout - requested_checkin
        
        # Récupérer les créneaux horaires valides (OBLIGATOIRES)
        valid_time_slots = self._get_valid_time_slots(
            rooms[0].room_type_id.id if rooms else None, 
            reservation_type_id
        )
        
        # Si des créneaux horaires sont définis, ils sont OBLIGATOIRES
        if valid_time_slots:
            _logger.info("[ALTERNATIVES] %d créneaux horaires OBLIGATOIRES détectés", len(valid_time_slots))
        
        alternatives = []
        
        # Fenêtre de recherche élargie
        search_start = max(requested_checkin, now)
        search_end = requested_checkout + timedelta(days=30)  # 30 jours de recherche
        
        for room in rooms:
            if len(alternatives) >= max_alternatives:
                break
            
            _logger.debug("[ALTERNATIVES] Analyse chambre %s", room.name)
            
            # Récupérer TOUS les séjours pour cette chambre dans la fenêtre
            stays = self.env['hotel.booking.stay'].search([
                ('room_id', '=', room.id),
                ('state', 'in', ['pending', 'ongoing']),
                ('actual_checkin_date', '<', search_end),
                ('actual_checkout_date', '>', search_start)
            ], order='actual_checkin_date')
            
            # Extraire les créneaux STRICTEMENT libres
            free_slots = self._extract_complete_free_slots_strict(
                room, stays, search_start, search_end,
                requested_duration, buffer_duration,
                valid_time_slots, now
            )
            
            _logger.debug("[ALTERNATIVES] %d créneaux libres trouvés pour chambre %s", 
                        len(free_slots), room.name)
            
            for slot in free_slots:
                if len(alternatives) >= max_alternatives:
                    break
                
                # Créer l'alternative avec validation stricte
                alt = self._create_alternative_slot_strict(
                    room, slot['start'], slot['end'],
                    requested_duration, valid_time_slots, now
                )
                
                if alt and not self._is_duplicate_alternative(alt, alternatives):
                    alternatives.append(alt)
                    _logger.info(
                        "[ALTERNATIVES] ✅ Alternative ajoutée: chambre=%s, %s → %s (durée=%sh)",
                        alt['room_name'], 
                        alt['checkin'].strftime('%d/%m/%Y %H:%M'),
                        alt['checkout'].strftime('%d/%m/%Y %H:%M'),
                        alt['duration_hours']
                    )
        
        # Trier par proximité avec la date demandée
        alternatives.sort(key=lambda x: abs((x['checkin'] - requested_checkin).total_seconds()))
        
        _logger.info("[ALTERNATIVES] %d alternatives VALIDES générées", len(alternatives))
        return alternatives[:max_alternatives]
    

    def _extract_complete_free_slots_strict(self, room, stays, window_start, window_end,
                                        requested_duration, buffer_duration,
                                        valid_time_slots, now):
        """
        Extrait UNIQUEMENT les créneaux STRICTEMENT libres:
        - Aucun chevauchement avec aucune réservation
        - Durée ÉGALE à la demande (tolérance 1h)
        - Respecte les créneaux horaires si définis
        - Date de début >= aujourd'hui
        
        NOUVELLE LOGIQUE:
        1. Trouve tous les gaps entre réservations
        2. Pour chaque gap, génère des créneaux possibles selon les horaires valides
        3. Vérifie que TOUT le créneau est libre (réservations + buffer)
        4. Ne retourne que les créneaux de durée appropriée
        
        :return: liste de dicts {'start', 'end', 'gap_size', 'matches_duration'}
        """
        free_slots = []
        
        # Ajuster le début de fenêtre si nécessaire
        window_start = max(window_start, now)
        
        if not stays:
            # Pas de réservation : toute la fenêtre est disponible
            _logger.debug("[FREE SLOTS] Aucune réservation, fenêtre entière disponible")
            slots = self._generate_slots_in_gap(
                window_start, window_end, requested_duration, 
                valid_time_slots, buffer_duration
            )
            return slots
        
        # Analyser les gaps entre réservations
        gaps = []
        
        # Gap avant la première réservation
        first_stay = stays[0]
        first_start_buffered = first_stay.actual_checkin_date - buffer_duration
        
        if window_start < first_start_buffered:
            gap_duration = first_start_buffered - window_start
            if gap_duration >= requested_duration:
                gaps.append({
                    'start': window_start,
                    'end': first_start_buffered,
                    'duration': gap_duration
                })
                _logger.debug(
                    "[FREE SLOTS] Gap avant 1ère résa: %s → %s (%.1fh)",
                    window_start.strftime('%d/%m %H:%M'),
                    first_start_buffered.strftime('%d/%m %H:%M'),
                    gap_duration.total_seconds() / 3600
                )
        
        # Gaps entre les réservations
        for i in range(len(stays) - 1):
            current_stay = stays[i]
            next_stay = stays[i + 1]
            
            gap_start = current_stay.actual_checkout_date + buffer_duration
            gap_end = next_stay.actual_checkin_date - buffer_duration
            
            if gap_end > gap_start:
                gap_duration = gap_end - gap_start
                if gap_duration >= requested_duration:
                    gaps.append({
                        'start': gap_start,
                        'end': gap_end,
                        'duration': gap_duration
                    })
                    _logger.debug(
                        "[FREE SLOTS] Gap entre résas: %s → %s (%.1fh)",
                        gap_start.strftime('%d/%m %H:%M'),
                        gap_end.strftime('%d/%m %H:%M'),
                        gap_duration.total_seconds() / 3600
                    )
        
        # Gap après la dernière réservation
        last_stay = stays[-1]
        last_end_buffered = last_stay.actual_checkout_date + buffer_duration
        
        if window_end > last_end_buffered:
            gap_duration = window_end - last_end_buffered
            if gap_duration >= requested_duration:
                gaps.append({
                    'start': last_end_buffered,
                    'end': window_end,
                    'duration': gap_duration
                })
                _logger.debug(
                    "[FREE SLOTS] Gap après dernière résa: %s → %s (%.1fh)",
                    last_end_buffered.strftime('%d/%m %H:%M'),
                    window_end.strftime('%d/%m %H:%M'),
                    gap_duration.total_seconds() / 3600
                )
        
        # Pour chaque gap, générer des créneaux respectant les horaires
        for gap in gaps:
            slots = self._generate_slots_in_gap(
                gap['start'], gap['end'], requested_duration,
                valid_time_slots, buffer_duration
            )
            
            # Vérifier que chaque slot généré ne chevauche AUCUNE réservation
            for slot in slots:
                if self._verify_slot_is_completely_free(
                    room, slot['start'], slot['end'], 
                    buffer_duration, stays
                ):
                    free_slots.append(slot)
                    _logger.debug(
                        "[FREE SLOTS] ✅ Slot validé: %s → %s",
                        slot['start'].strftime('%d/%m %H:%M'),
                        slot['end'].strftime('%d/%m %H:%M')
                    )
                else:
                    _logger.debug(
                        "[FREE SLOTS] ❌ Slot rejeté (chevauchement): %s → %s",
                        slot['start'].strftime('%d/%m %H:%M'),
                        slot['end'].strftime('%d/%m %H:%M')
                    )
        
        return free_slots

    

    def _generate_slots_in_gap(self, gap_start, gap_end, requested_duration,
                           valid_time_slots, buffer_duration):
        """
        Génère tous les créneaux possibles dans un gap en respectant:
        - Les horaires valides (si définis)
        - La durée demandée
        - Aucun dépassement du gap
        
        :return: liste de créneaux possibles
        """
        slots = []
        
        if not valid_time_slots:
            # Pas de contrainte horaire : créneau simple au début du gap
            slot_end = gap_start + requested_duration
            if slot_end <= gap_end:
                slots.append({
                    'start': gap_start,
                    'end': slot_end,
                    'gap_size': gap_end - gap_start,
                    'matches_duration': True
                })
            return slots
        
        # Avec contraintes horaires : générer un créneau par jour du gap
        current_date = gap_start.date()
        gap_end_date = gap_end.date()
        
        while current_date <= gap_end_date:
            for time_slot in valid_time_slots:
                # Créer le début du créneau avec l'horaire valide
                slot_start = datetime.combine(current_date, time_slot['checkin_time'])
                
                # S'assurer que le début est dans le gap
                if slot_start < gap_start:
                    slot_start = gap_start
                
                # Calculer la fin
                slot_end = slot_start + requested_duration
                
                # Vérifier que le créneau tient dans le gap
                if slot_end <= gap_end and slot_start >= gap_start:
                    # Vérifier que l'horaire de fin respecte aussi les contraintes
                    if self._is_valid_checkout_time(slot_end, time_slot['checkout_time']):
                        slots.append({
                            'start': slot_start,
                            'end': slot_end,
                            'gap_size': gap_end - gap_start,
                            'matches_duration': True
                        })
            
            current_date += timedelta(days=1)
        
        return slots


    def _is_valid_checkout_time(self, checkout_datetime, valid_checkout_time):
        """
        Vérifie si l'heure de checkout est valide.
        Autorise un checkout à n'importe quelle heure si elle est avant ou égale à l'heure valide.
        """
        checkout_time = checkout_datetime.time()
        
        # Convertir en minutes pour comparaison
        checkout_minutes = checkout_time.hour * 60 + checkout_time.minute
        valid_minutes = valid_checkout_time.hour * 60 + valid_checkout_time.minute
        
        # Tolérance de 1 heure
        return abs(checkout_minutes - valid_minutes) <= 60


    def _verify_slot_is_completely_free(self, room, slot_start, slot_end,
                                        buffer_duration, stays):
        """
        Vérifie qu'un créneau est COMPLÈTEMENT libre (aucun chevauchement).
        
        VÉRIFICATION STRICTE:
        - Le créneau + buffer ne doit chevaucher AUCUNE réservation + buffer
        
        :return: True si complètement libre, False sinon
        """
        slot_start_buffered = slot_start - buffer_duration
        slot_end_buffered = slot_end + buffer_duration
        
        for stay in stays:
            stay_start_buffered = stay.actual_checkin_date - buffer_duration
            stay_end_buffered = stay.actual_checkout_date + buffer_duration
            
            # Vérifier le chevauchement
            if self._check_overlap(
                slot_start_buffered, slot_end_buffered,
                stay_start_buffered, stay_end_buffered
            ):
                _logger.debug(
                    "[VERIFY] ❌ Chevauchement détecté avec stay_id=%s (%s → %s)",
                    stay.id,
                    stay.actual_checkin_date.strftime('%d/%m %H:%M'),
                    stay.actual_checkout_date.strftime('%d/%m %H:%M')
                )
                return False
        
        return True



    def _create_alternative_slot_strict(self, room, start, end, requested_duration,
                                    valid_time_slots, now):
        """
        Crée un créneau alternatif avec validation STRICTE:
        1. Date >= aujourd'hui
        2. Durée ÉGALE à la demande (tolérance 1h)
        3. Horaires valides SI définis
        
        REJET IMMÉDIAT si:
        - Date passée
        - Durée incorrecte
        - Horaires non conformes
        
        :return: dict alternative ou None si invalide
        """
        # RÈGLE 1: Pas de dates passées
        if start < now:
            _logger.debug("[CREATE ALT] ❌ Rejeté: date passée")
            return None
        
        if end <= start:
            _logger.debug("[CREATE ALT] ❌ Rejeté: end <= start")
            return None
        
        actual_duration = end - start
        
        # RÈGLE 4: Durée STRICTEMENT égale (tolérance 1h)
        duration_diff = abs((actual_duration - requested_duration).total_seconds())
        tolerance_seconds = 3600  # 1 heure
        
        if duration_diff > tolerance_seconds:
            _logger.debug(
                "[CREATE ALT] ❌ Rejeté: durée incorrecte (demandé=%.1fh, proposé=%.1fh, diff=%.1fh)",
                requested_duration.total_seconds() / 3600,
                actual_duration.total_seconds() / 3600,
                duration_diff / 3600
            )
            return None
        
        
        # RÈGLE 2: Vérifier les horaires valides SI définis
        if valid_time_slots:
            if not self._is_slot_within_valid_times(start, end, valid_time_slots):
                _logger.debug("[CREATE ALT] ❌ Rejeté: horaires non conformes")
                return None
        
        matches_duration = duration_diff <= tolerance_seconds
        
        alternative = {
            'room_id': room.id,
            'room_name': room.name,
            'checkin': start,
            'checkout': end,
            'duration_hours': round(actual_duration.total_seconds() / 3600, 2),
            'matches_duration': matches_duration,
            'priority': 1,  # Toutes les alternatives strictes ont la même priorité
            'score': 100
        }
        
        _logger.debug(
            "[CREATE ALT] ✅ Alternative créée: %s | %s → %s | %.2fh",
            room.name,
            start.strftime('%d/%m/%Y %H:%M'),
            end.strftime('%d/%m/%Y %H:%M'),
            alternative['duration_hours']
        )
        
        return alternative


    def _is_slot_within_valid_times(self, start, end, valid_time_slots):
        """
        Vérifie qu'un créneau respecte les horaires valides.
        
        :return: True si les horaires sont conformes, False sinon
        """
        start_time = start.time()
        end_time = end.time()
        
        for time_slot in valid_time_slots:
            valid_checkin = time_slot['checkin_time']
            valid_checkout = time_slot['checkout_time']
            
            # Tolérance de 1 heure
            checkin_ok = abs(
                (start_time.hour * 60 + start_time.minute) - 
                (valid_checkin.hour * 60 + valid_checkin.minute)
            ) <= 60
            
            checkout_ok = abs(
                (end_time.hour * 60 + end_time.minute) - 
                (valid_checkout.hour * 60 + valid_checkout.minute)
            ) <= 60
            
            if checkin_ok and checkout_ok:
                return True
        
        return False
   
   
   
    def _is_duplicate_alternative(self, new_alt, existing_alternatives):
        """Vérifie si une alternative est un doublon"""
        for alt in existing_alternatives:
            if (alt['room_id'] == new_alt['room_id'] and
                alt['checkin'] == new_alt['checkin'] and
                alt['checkout'] == new_alt['checkout']):
                return True
        return False

    def _get_valid_time_slots(self, room_type_id, reservation_type_id):
        """
        Récupère les créneaux horaires valides pour le type de réservation.
        """
        if not reservation_type_id or not room_type_id:
            return []
        
        slots = self.env['hotel.room.reservation.slot'].search([
            ('room_type_id', '=', room_type_id),
            ('reservation_type_id', '=', reservation_type_id)
        ])
        
        valid_slots = []
        for slot in slots:
            valid_slots.append({
                'checkin_time': self._float_to_time(slot.checkin_time),
                'checkout_time': self._float_to_time(slot.checkout_time)
            })
        
        _logger.debug("[TIME SLOTS] %d créneaux valides trouvés", len(valid_slots))
        return valid_slots

    def _float_to_time(self, float_hour):
        """Convertit un float en time (ex: 14.5 -> 14:30)"""
        from datetime import time
        hours = int(float_hour)
        minutes = int(round((float_hour - hours) * 60))
        return time(hour=hours, minute=minutes)

    def _adjust_to_valid_times(self, start, end, requested_duration, valid_time_slots):
        """
        Ajuste les dates/heures pour qu'elles correspondent aux créneaux valides.
        """
        if not valid_time_slots:
            return start, end
        
        # Essayer chaque créneau horaire valide
        for time_slot in valid_time_slots:
            # Créer des datetime avec les horaires du slot
            adjusted_start = datetime.combine(start.date(), time_slot['checkin_time'])
            
            # Si l'heure d'arrivée valide est avant le début du gap, prendre le lendemain
            if adjusted_start < start:
                adjusted_start = datetime.combine(
                    (start + timedelta(days=1)).date(), 
                    time_slot['checkin_time']
                )
            
            # Calculer la fin en fonction de la durée demandée
            adjusted_end = adjusted_start + requested_duration
            
            # Vérifier que le créneau ajusté reste dans les limites
            if adjusted_start >= start and adjusted_end <= end:
                return adjusted_start, adjusted_end
        
        # Aucun créneau horaire valide ne convient
        return None, None

    # ==================== MÉTHODES PRIVÉES - CONSTRUCTION RÉPONSES ====================

    def _build_available_response(self, room):
        """Construit la réponse en cas de disponibilité"""
        return {
            'status': 'available',
            'room_id': room.id,
            'room_name': room.name,
            'message': _("Chambre %s disponible") % room.name,
            'alternatives': [],
            'conflict_details': []
        }

    def _build_unavailable_response(self, message, alternatives, reason='unavailable', conflict_details=None):
        """Construit la réponse en cas d'indisponibilité avec détails"""
        return {
            'status': 'unavailable',
            'room_id': None,
            'room_name': None,
            'message': message,
            'alternatives': alternatives,
            'reason': reason,
            'conflict_details': conflict_details or [],
            'total_alternatives': len(alternatives)
        }