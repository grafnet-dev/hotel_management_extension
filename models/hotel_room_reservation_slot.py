from odoo import models, fields
from odoo.exceptions import ValidationError
from odoo import api
class HotelRoomReservationSlot(models.Model):
    _name = "hotel.room.reservation.slot"
    _description = "Créneau horaire personnalisé pour type de réservation"

    room_id = fields.Many2one('hotel.room', string="Chambre", required=True, ondelete="cascade")
    reservation_type_id = fields.Many2one('hotel.reservation.type', string="Type de réservation", required=True, ondelete="cascade")
    
    checkin_time = fields.Float(string="Heure d'arrivée", required=True)
    checkout_time = fields.Float(string="Heure de départ", required=True)
    
    name = fields.Char(string="Nom du créneau", compute="_compute_name", store=True)

    @api.depends('reservation_type_id', 'checkin_time', 'checkout_time')
    def _compute_name(self):
        for rec in self:
            rec.name = f"{rec.reservation_type_id.name or ''} : {rec.checkin_time}h - {rec.checkout_time}h"
    #Contrainte d’unicité SQL : une chambre ne peut pas avoir deux fois le même créneau pour un type donné
    _sql_constraints = [
    (
        'unique_slot_per_room_type_time',
        'UNIQUE(room_id, reservation_type_id, checkin_time, checkout_time)',
        'Un créneau identique existe déjà pour ce type de réservation dans cette chambre.'
    )
    ]
    #Contrainte Python : on interdit de créer un créneau si le type de réservation est flexible
    @api.constrains('reservation_type_id', 'checkin_time', 'checkout_time')
    def _check_slot_for_flexible_type(self):
        for slot in self:
            if slot.reservation_type_id.is_flexible:
                raise ValidationError(
                    f"Impossible de définir un créneau horaire pour le type flexible '{slot.reservation_type_id.name}'."
                )
    
    @api.onchange('room_id')
    def _onchange_room_id(self):
        if self.room_id:
            return {
                'domain': {
                    'reservation_type_id': [('id', 'in', self.room_id.reservation_type_ids.ids)]
                }
            }
            
    # Contraintes de validation
    @api.constrains('reservation_type_id', 'checkin_time', 'checkout_time')
    def _check_slot_validation(self):
        for slot in self:
            # Vérifier que le type n'est pas flexible
            if slot.reservation_type_id.is_flexible:
                raise ValidationError(
                    f"Impossible de définir un créneau horaire pour le type flexible '{slot.reservation_type_id.name}'."
                )
            
            # Vérifier que le type est accepté par la chambre
            if slot.reservation_type_id not in slot.room_id.reservation_type_ids:
                raise ValidationError(
                    f"Le type de réservation '{slot.reservation_type_id.name}' n'est pas accepté par cette chambre."
                )