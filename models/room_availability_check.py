"""
Moteur de vérification de disponibilité des chambres d'hôtel
Gère l'attribution automatique et la détection de conflits de réservation
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
    - Proposer des alternatives en cas d'indisponibilité
    - Gérer les buffers de nettoyage entre réservations
    """
    _name = 'hotel.room.availability.engine'
    _description = 'Moteur de disponibilité des chambres'

    # ==================== MÉTHODES PUBLIQUES ====================

    @api.model
    def check_availability(self, room_type_id, checkin_date, checkout_date, 
                          exclude_stay_id=None, buffer_hours=None):
        """
        Point d'entrée principal : vérifie la disponibilité et retourne une chambre.
        
        :param room_type_id: ID du type de chambre recherché
        :param checkin_date: datetime de début de séjour
        :param checkout_date: datetime de fin de séjour
        :param exclude_stay_id: ID du séjour à exclure (pour modification)
        :param buffer_hours: heures de marge pour le nettoyage
        :return: dict avec status, room_id, message, alternatives
        """
        _logger.info(
            "[AVAILABILITY] Début vérification | type=%s | in=%s | out=%s",
            room_type_id, checkin_date, checkout_date, buffer_hours
        )

        # 1-Validation des entrées
        validation_result = self._validate_inputs(
            room_type_id, checkin_date, checkout_date
        )
        if not validation_result['valid']:
            return validation_result

        #2- Récupérer toutes les chambres du type demandé
        rooms = self._get_rooms_by_type(room_type_id)
        
        if not rooms:
            return self._build_unavailable_response(
                message=_("Aucune chambre de ce type n'existe dans le système."),
                alternatives=[]
            )

        # Calculer le buffer
        buffer_duration = timedelta(hours=buffer_hours) if buffer_hours else timedelta(0)
        _logger.debug("[AVAILABILITY] Buffer appliqué : %s", buffer_duration)

        # Parcourir les chambres pour trouver une disponible (ici gérer correctement l'objet conflict)
        for room in rooms:
            is_available, conflict = self._check_room_availability(
                room, checkin_date, checkout_date, 
                buffer_duration, exclude_stay_id
            )
            
            if is_available:
                _logger.info(
                    "[AVAILABILITY] ✅ Chambre trouvée | room_id=%s | num=%s",
                    room.id, room.name
                )
                return self._build_available_response(room)

        # Aucune chambre disponible : chercher des alternatives
        _logger.warning(
            "[AVAILABILITY] ❌ Aucune chambre disponible | type=%s",
            room_type_id
        )
        
        alternatives = self._find_alternative_slots(
            room_type_id, checkin_date, checkout_date, buffer_duration
        )
        
        return self._build_unavailable_response(
            message=_("Toutes les chambres sont occupées pour cette période."),
            alternatives=alternatives
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

    def _get_occupied_slots(self, room, start_date, end_date):
        """
        Récupère tous les créneaux occupés pour une chambre sur une période.
        
        :return: liste de dict avec start, end, stay_id, booking_ref
        """
        stays = self.env['hotel.booking.stay'].search([
            ('room_id', '=', room.id),
            ('state', 'in', ['pending', 'ongoing']),
            ('actual_checkin_date', '<', end_date),
            ('actual_checkout_date', '>', start_date)
        ], order='actual_checkin_date')
        
        occupied_slots = []
        for stay in stays:
            occupied_slots.append({
                'start': stay.actual_checkin_date,
                'end': stay.actual_checkout_date,
                'stay_id': stay.id,
                'booking_ref': stay.booking_id.reservation_no if stay.booking_id else None,
                'guest_name': ', '.join(stay.occupant_ids.mapped('name')) or _('Non renseigné')
            })
        
        return occupied_slots

    # ==================== MÉTHODES PRIVÉES - LOGIQUE DISPONIBILITÉ ====================

    def _check_room_availability(self, room, checkin_date, checkout_date, 
                             buffer_duration, exclude_stay_id=None):
        """
        Vérifie si une chambre est disponible pour la période demandée.
        Si buffer_duration = 0, aucune marge de nettoyage n'est appliquée.
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
        
        existing_stays = self.env['hotel.booking.stay'].search(domain)

        # Appliquer le buffer seulement si défini
        requested_start_buffered = checkin_date - buffer_duration
        requested_end_buffered = checkout_date + buffer_duration

        for stay in existing_stays:
            stay_start = stay.actual_checkin_date
            stay_end = stay.actual_checkout_date

            stay_start_buffered = stay_start - buffer_duration
            stay_end_buffered = stay_end + buffer_duration

            has_overlap = self._check_overlap(
                requested_start_buffered, requested_end_buffered,
                stay_start_buffered, stay_end_buffered
            )

            if has_overlap:
                _logger.debug(
                    "[CHECK] ❌ Conflit avec stay_id=%s | %s → %s",
                    stay.id, stay_start, stay_end
                )
                return False, {
                    'stay_id': stay.id,
                    'checkin': stay_start,
                    'checkout': stay_end,
                    'booking_ref': stay.booking_id.reservation_no if stay.booking_id else None
                }

        _logger.debug("[CHECK] ✅ Chambre disponible=%s", room.name)
        return True, None


    def _check_overlap(self, start1, end1, start2, end2):
        """
        Vérifie si deux périodes se chevauchent.
        
        Logique: deux périodes se chevauchent si:
        - start1 < end2 ET start2 < end1
        """
        return start1 < end2 and start2 < end1

    # ==================== MÉTHODES PRIVÉES - ALTERNATIVES ====================

    def _find_alternative_slots(self, room_type_id, requested_checkin, 
                                requested_checkout, buffer_duration, max_alternatives=3):
        """
        Trouve des créneaux alternatifs proches de la période demandée.
        
        :return: liste de dict avec start, end, room_id, room_name
        """
        _logger.info("[ALTERNATIVES] Recherche de créneaux alternatifs")
        
        rooms = self._get_rooms_by_type(room_type_id)
        alternatives = []
        
        # Définir une fenêtre de recherche (±7 jours)
        search_window_start = requested_checkin - timedelta(days=7)
        search_window_end = requested_checkout + timedelta(days=7)
        
        for room in rooms:
            # Récupérer tous les séjours dans la fenêtre
            stays = self.env['hotel.booking.stay'].search([
                ('room_id', '=', room.id),
                ('state', 'in', ['pending', 'ongoing']),
                ('actual_checkin_date', '<', search_window_end),
                ('actual_checkout_date', '>', search_window_start)
            ], order='actual_checkin_date')
            
            # Chercher les créneaux libres
            available_slots = self._extract_free_slots(
                stays, search_window_start, search_window_end,
                requested_checkin, requested_checkout, buffer_duration
            )
            
            for slot in available_slots:
                alternatives.append({
                    'room_id': room.id,
                    'room_name': room.name,
                    'checkin': slot['start'],
                    'checkout': slot['end'],
                    'duration_hours': (slot['end'] - slot['start']).total_seconds() / 3600
                })
                
                if len(alternatives) >= max_alternatives:
                    return alternatives[:max_alternatives]
        
        return alternatives[:max_alternatives]

    def _extract_free_slots(self, stays, window_start, window_end, 
                       requested_checkin, requested_checkout, buffer_duration):
        """
        Extrait les créneaux libres entre les réservations existantes.
        Si buffer_duration = 0, on ignore les marges.
        """
        requested_duration = requested_checkout - requested_checkin
        free_slots = []

        if not stays:
            return [{'start': window_start, 'end': window_end}]

        # Avant la première réservation
        first_stay = stays[0]
        first_start_buffered = first_stay.actual_checkin_date - buffer_duration if buffer_duration else first_stay.actual_checkin_date

        if window_start < first_start_buffered:
            potential_end = min(first_start_buffered, window_end)
            if (potential_end - window_start) >= requested_duration:
                free_slots.append({'start': window_start, 'end': potential_end})

        # Entre les réservations
        for i in range(len(stays) - 1):
            current_stay = stays[i]
            next_stay = stays[i + 1]

            gap_start = current_stay.actual_checkout_date + buffer_duration if buffer_duration else current_stay.actual_checkout_date
            gap_end = next_stay.actual_checkin_date - buffer_duration if buffer_duration else next_stay.actual_checkin_date

            if gap_end > gap_start and (gap_end - gap_start) >= requested_duration:
                free_slots.append({'start': gap_start, 'end': gap_end})

        # Après la dernière
        last_stay = stays[-1]
        last_end_buffered = last_stay.actual_checkout_date + buffer_duration if buffer_duration else last_stay.actual_checkout_date

        if window_end > last_end_buffered:
            potential_start = max(last_end_buffered, window_start)
            if (window_end - potential_start) >= requested_duration:
                free_slots.append({'start': potential_start, 'end': window_end})

        return free_slots


    # ==================== MÉTHODES PRIVÉES - CONSTRUCTION RÉPONSES ====================

    def _build_available_response(self, room):
        """Construit la réponse en cas de disponibilité"""
        return {
            'status': 'available',
            'room_id': room.id,
            'room_name': room.name,
            'message': _("Chambre %s disponible") % room.name,
            'alternatives': []
        }

    def _build_unavailable_response(self, message, alternatives):
        """Construit la réponse en cas d'indisponibilité"""
        return {
            'status': 'unavailable',
            'room_id': None,
            'room_name': None,
            'message': message,
            'alternatives': alternatives
        }