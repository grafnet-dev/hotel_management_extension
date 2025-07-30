from odoo import models, fields, tools
from datetime import datetime, timedelta
from odoo.exceptions import UserError
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta

class HotelRoomPlanning(models.Model):
    _name = 'hotel.room.planning'
    _description = 'Vue Planning des Chambres d\'Hôtel'
    _auto = False  # Vue non persistée
    
    # Champs pour l'affichage du planning
    room_id = fields.Many2one('hotel.room', string='Chambre')
    room_name = fields.Char(string='Nom Chambre')
    room_type_id = fields.Many2one('hotel.room.type', string='Type de Chambre')
    room_type_name = fields.Char(string='Type')
    base_price = fields.Float(related='room_type_id.base_price',string="Prix de base")
    date = fields.Date(string='Date')
    status = fields.Selection([
        ('available', 'Disponible'),
        ('reserved', 'Réservé'),
        ('occupied', 'Occupé'),
        ('checkout', 'Départ'),
        ('checkin', 'Arrivée'),
        ('maintenance', 'Maintenance'),
        ('cleaning', 'Nettoyage'),
        ('out_of_order', 'Hors Service'),
    ], string='Statut')
    
    reservation_id = fields.Many2one('room.booking.line', string='Réservation')
    reservation_ref = fields.Char(string='Référence')
    guest_name = fields.Char(string='Client')
    
    def init(self):
        """Initialise la vue SQL"""
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT 
                    row_number() OVER () AS id,
                    r.id as room_id,
                    r.name as room_name,
                    rt.id as room_type_id,
                    rt.name as room_type_name,
                    d.date as date,
                    CASE 
                        WHEN r.is_in_maintenance THEN 'maintenance'
                        WHEN r.status = 'cleaning' THEN 'cleaning'
                        WHEN r.status = 'out_of_order' THEN 'out_of_order'
                        WHEN rbl.id IS NOT NULL THEN 
                            CASE 
                                WHEN d.date = rbl.checkin_date::date THEN 'checkin'
                                WHEN d.date = rbl.checkout_date::date THEN 'checkout'
                                ELSE 'occupied'
                            END
                        ELSE 'available'
                    END as status,
                    rbl.id as reservation_id
                FROM hotel_room r
                JOIN hotel_room_type rt ON r.room_type_id = rt.id
                CROSS JOIN generate_series(
                    CURRENT_DATE - INTERVAL '30 days',
                    CURRENT_DATE + INTERVAL '90 days',
                    '1 day'::interval
                ) d(date)
                LEFT JOIN room_booking_line rbl ON (
                    r.id = rbl.room_id 
                    AND d.date >= rbl.checkin_date::date 
                    AND d.date < rbl.checkout_date::date
                   
                )
                WHERE rt.active = true
                ORDER BY rt.sequence, rt.name, r.name, d.date
            )
        """ % self._table)

class HotelRoomPlanningWizard(models.TransientModel):
    _name = 'hotel.room.planning.wizard'
    _description = 'Assistant Planning Chambres'
    
    date_from = fields.Date(
        string='Date de début', 
        default=fields.Date.today,
        required=True
    )
    date_to = fields.Date(
        string='Date de fin', 
        default=lambda self: fields.Date.today() + timedelta(days=30),
        required=True
    )
    room_type_ids = fields.Many2many(
        'hotel.room.type', 
        string='Types de chambres',
        help='Laisser vide pour afficher tous les types'
    )
    view_mode = fields.Selection([
        ('week', 'Vue Semaine'),
        ('month', 'Vue Mois'),
        ('quarter', 'Vue Trimestre'),
    ], string='Mode d\'affichage', default='month')
    
    #def action_show_planning(self):
       # """Ouvre la vue planning avec les filtres appliqués"""
        #domain = [
         #   ('date', '>=', self.date_from),
         #   ('date', '<=', self.date_to),
        #]
        
        #if self.room_type_ids:
            #domain.append(('room_type_id', 'in', self.room_type_ids.ids))
        
        #return {
            #'name': f'Planning Chambres - {self.date_from} au {self.date_to}',
            #'type': 'ir.actions.act_window',
            #'res_model': 'hotel.room.planning',
            #'view_mode': 'pivot,tree',
            #'domain': domain,
            #'context': {
                #'group_by': ['room_type_name', 'room_name', 'date'],
                #'pivot_measures': ['__count'],
                #'pivot_column_groupby': ['date'],
                #'pivot_row_groupby': ['room_type_name', 'room_name'],
            #},
        #}
    

    def action_show_planning(self):
        """Ouvre la vue planning avec les filtres appliqués"""
        domain = [
            ('date', '>=', self.date_from),
            ('date', '<=', self.date_to),
        ]
        
        if self.room_type_ids:
            domain.append(('room_type_id', 'in', self.room_type_ids.ids))
        
        today = date.today()
        start_week = today - timedelta(days=today.weekday())  # Lundi
        end_week = start_week + timedelta(days=7)             # Lundi suivant
        start_month = today.replace(day=1)
        end_month = (start_month + relativedelta(months=1))   # 1er du mois suivant

        return {
            'name': f'Planning Chambres - {self.date_from} au {self.date_to}',
            'type': 'ir.actions.act_window',
            'res_model': 'hotel.room.planning',
            'view_mode': 'pivot,tree',
            'domain': domain,
            'context': {
                'group_by': ['room_type_name', 'room_name', 'date'],
                'pivot_measures': ['__count'],
                'pivot_column_groupby': ['date'],
                'pivot_row_groupby': ['room_type_name', 'room_name'],

                # Contexte pour les filtres dynamiques
                'today': today.isoformat(),
                'start_week': start_week.isoformat(),
                'end_week': end_week.isoformat(),
                'start_month': start_month.isoformat(),
                'end_month': end_month.isoformat(),
            },
        }


# Extension du modèle hotel.room pour ajouter des méthodes utiles
class HotelRoomExtended(models.Model):
    _inherit = 'hotel.room'
    
    def get_status_for_date(self, target_date):
        """Retourne le statut d'une chambre pour une date donnée"""
        self.ensure_one()
        
        if self.is_in_maintenance:
            return 'maintenance'
        
        if self.status in ['cleaning', 'out_of_order']:
            return self.status
            
        # Cherche une réservation active pour cette date
        reservation = self.env['room.booking.line'].search([
            ('room_id', '=', self.id),
            ('checkin_date', '<=', target_date),
            ('checkout_date', '>', target_date),
            ('state', 'in', ['reserved', 'done'])
        ], limit=1)
        
        if reservation:
            if target_date == reservation.checkin_date.date():
                return 'checkin'
            elif target_date == (reservation.checkout_date.date() - timedelta(days=1)):
                return 'checkout'
            elif reservation.state == 'reserved':
                return 'reserved'
            else:
                return 'occupied'
        
        return 'available'
    
    def action_open_planning(self):
        """Action pour ouvrir le planning d'une chambre"""
        return {
            'name': f'Planning - {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'hotel.room.planning.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_room_type_ids': [(6, 0, [self.room_type_id.id])]},
        }

class HotelRoomTypeExtended(models.Model):
    _inherit = 'hotel.room.type'
    
    def action_open_planning(self):
        """Action pour ouvrir le planning d'un type de chambre"""
        return {
            'name': f'Planning - {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'hotel.room.planning.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_room_type_ids': [(6, 0, [self.id])]},
        }
    
    