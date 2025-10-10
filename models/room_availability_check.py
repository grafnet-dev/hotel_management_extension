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
        """Valide les paramètres d'entrée"""
        if not room_type_id:
            return {
                'valid': False,
                'status': 'error',
                'message': _("Le type de chambre est obligatoire.")
            }
        
        if not checkin_date or not checkout_date:
            return {
                'valid': False,
                'status': 'error',
                'message': _("Les dates de check-in et check-out sont obligatoires.")
            }
        
        if not isinstance(checkin_date, datetime) or not isinstance(checkout_date, datetime):
            return {
                'valid': False,
                'status': 'error',
                'message': _("Les dates doivent être des objets datetime.")
            }
        
        if checkout_date <= checkin_date:
            return {
                'valid': False,
                'status': 'error',
                'message': _("La date de départ doit être après la date d'arrivée.")
            }
        
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
        Génère des alternatives INTELLIGENTES basées sur:
        1. La chambre qui se libère le plus tôt
        2. Les créneaux complètement libres (pas de chevauchement partiel)
        3. La durée demandée
        4. Les horaires valides du type de réservation
        
        :return: liste limitée à max_alternatives (3 par défaut)
        """
        _logger.info("[ALTERNATIVES] Génération de %d alternatives intelligentes", max_alternatives)
        
        now = datetime.now()
        requested_duration = requested_checkout - requested_checkin
        
        # Récupérer les créneaux horaires valides
        valid_time_slots = self._get_valid_time_slots(
            rooms[0].room_type_id.id if rooms else None, 
            reservation_type_id
        )
        
        alternatives = []
        
        # STRATÉGIE 1: Proposer après la libération la plus proche
        if earliest_liberation:
            start_after_liberation = earliest_liberation['liberation_date']
            
            # S'assurer que la date n'est pas dans le passé
            if start_after_liberation < now:
                start_after_liberation = now
            
            end_after_liberation = start_after_liberation + requested_duration
            
            # Vérifier la disponibilité de cette période
            for room in rooms:
                is_available, _ = self._check_room_availability(
                    room, start_after_liberation, end_after_liberation,
                    buffer_duration, None
                )
                
                if is_available:
                    alt = self._create_alternative_slot(
                        room, start_after_liberation, end_after_liberation,
                        requested_duration, valid_time_slots, now,
                        priority=1  # Haute priorité car basé sur libération proche
                    )
                    if alt:
                        alternatives.append(alt)
                        break  # Une seule alternative de ce type
        
        # STRATÉGIE 2: Chercher dans une fenêtre élargie
        search_start = max(requested_checkin, now)
        search_end = requested_checkout + timedelta(days=14)  # Fenêtre de 2 semaines
        
        for room in rooms:
            if len(alternatives) >= max_alternatives:
                break
            
            # Récupérer tous les séjours pour cette chambre
            stays = self.env['hotel.booking.stay'].search([
                ('room_id', '=', room.id),
                ('state', 'in', ['pending', 'ongoing']),
                ('actual_checkin_date', '<', search_end),
                ('actual_checkout_date', '>', search_start)
            ], order='actual_checkin_date')
            
            # Extraire les créneaux COMPLÈTEMENT libres
            free_slots = self._extract_complete_free_slots(
                stays, search_start, search_end,
                requested_duration, buffer_duration
            )
            
            for slot in free_slots:
                if len(alternatives) >= max_alternatives:
                    break
                
                alt = self._create_alternative_slot(
                    room, slot['start'], slot['end'],
                    requested_duration, valid_time_slots, now,
                    priority=2
                )
                if alt and not self._is_duplicate_alternative(alt, alternatives):
                    alternatives.append(alt)
        
        # Trier par priorité et date
        alternatives.sort(key=lambda x: (
            x['priority'],
            abs((x['checkin'] - requested_checkin).total_seconds())
        ))
        
        _logger.info("[ALTERNATIVES] %d alternatives générées", len(alternatives))
        return alternatives[:max_alternatives]

    def _extract_complete_free_slots(self, stays, window_start, window_end,
                                     requested_duration, buffer_duration):
        """
        Extrait uniquement les créneaux COMPLÈTEMENT libres, sans aucun chevauchement.
        RÈGLE: Le créneau doit pouvoir accueillir la durée entière demandée.
        """
        free_slots = []
        
        if not stays:
            # Pas de réservation : toute la fenêtre est disponible
            gap_duration = window_end - window_start
            if gap_duration >= requested_duration:
                free_slots.append({
                    'start': window_start,
                    'end': window_start + requested_duration,
                    'gap_size': gap_duration
                })
            return free_slots
        
        # Avant la première réservation
        first_stay = stays[0]
        first_start_buffered = first_stay.actual_checkin_date - buffer_duration
        
        if window_start < first_start_buffered:
            gap_duration = first_start_buffered - window_start
            if gap_duration >= requested_duration:
                free_slots.append({
                    'start': window_start,
                    'end': window_start + requested_duration,
                    'gap_size': gap_duration
                })
        
        # Entre les réservations (STRICTEMENT entre, sans chevauchement)
        for i in range(len(stays) - 1):
            current_stay = stays[i]
            next_stay = stays[i + 1]
            
            gap_start = current_stay.actual_checkout_date + buffer_duration
            gap_end = next_stay.actual_checkin_date - buffer_duration
            
            if gap_end > gap_start:
                gap_duration = gap_end - gap_start
                # Vérifier que le gap peut contenir ENTIÈREMENT la durée demandée
                if gap_duration >= requested_duration:
                    free_slots.append({
                        'start': gap_start,
                        'end': gap_start + requested_duration,
                        'gap_size': gap_duration
                    })
        
        # Après la dernière réservation
        last_stay = stays[-1]
        last_end_buffered = last_stay.actual_checkout_date + buffer_duration
        
        if window_end > last_end_buffered:
            gap_duration = window_end - last_end_buffered
            if gap_duration >= requested_duration:
                free_slots.append({
                    'start': last_end_buffered,
                    'end': last_end_buffered + requested_duration,
                    'gap_size': gap_duration
                })
        
        return free_slots

    def _create_alternative_slot(self, room, start, end, requested_duration, 
                                 valid_time_slots, now, priority=2):
        """
        Crée un créneau alternatif en respectant toutes les contraintes.
        """
        # Ne pas proposer de dates passées
        if start < now:
            start = now
        
        if end <= start:
            return None
        
        # Ajuster aux horaires valides si nécessaire
        if valid_time_slots:
            adjusted_start, adjusted_end = self._adjust_to_valid_times(
                start, end, requested_duration, valid_time_slots
            )
            if not adjusted_start or not adjusted_end:
                return None
            start = adjusted_start
            end = adjusted_end
        
        # Vérifier que la durée minimale est respectée
        actual_duration = end - start
        if actual_duration < requested_duration:
            return None
        
        matches_duration = abs(actual_duration - requested_duration) < timedelta(hours=1)
        
        return {
            'room_id': room.id,
            'room_name': room.name,
            'checkin': start,
            'checkout': end,
            'duration_hours': actual_duration.total_seconds() / 3600,
            'matches_duration': matches_duration,
            'priority': priority,
            'score': 100 if matches_duration else 50
        }

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