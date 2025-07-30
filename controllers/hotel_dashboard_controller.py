# File: hotel_dashboard/controllers/hotel_dashboard_controller.py
from odoo import http
from odoo.http import request
from odoo.exceptions import AccessError
import json
from datetime import datetime, timedelta

class HotelDashboardController(http.Controller):

    @http.route('/hotel/dashboard', type='http', auth='user', website=True)
    def dashboard(self, **kw):
        return request.render('hotel_dashboard.hotel_dashboard_template')

    @http.route('/hotel/dashboard/data', type='json', auth='user')
    def get_dashboard_data(self, start=None, end=None, filter_status=None):
        """
        Returns JSON data for dashboard:
        - KPIs
        - Rooms and room types with rooms list
        - Reservations data for calendar (filtered by date range and status)
        """

        # Parse dates
        if not start or not end:
            today = datetime.today().date()
            start = (today.replace(day=1)).strftime('%Y-%m-%d')
            next_month = (today.replace(day=28) + timedelta(days=4)).replace(day=1)
            end = (next_month - timedelta(days=1)).strftime('%Y-%m-%d')

        domain_reservation = [
            ('check_in_date', '<=', end),
            ('check_out_date', '>=', start),
        ]
        if filter_status and filter_status != 'all':
            domain_reservation.append(('status', '=', filter_status))

        Reservation = request.env['hotel.reservation'].sudo()
        Room = request.env['hotel.room'].sudo()
        RoomType = request.env['room.type'].sudo()

        # Calculate KPIs
        total_confirmed = Reservation.search_count([('status', '=', 'confirmed')])
        total_checkout = Reservation.search_count([('status', '=', 'checkout')])
        today_date = datetime.today().date()
        # Rooms available today: rooms that have no reservation overlapping today with status in ('booking','confirmed','checked_in')
        occupied_room_ids = Reservation.search([
            ('check_in_date', '<=', today_date),
            ('check_out_date', '>=', today_date),
            ('status', 'in', ['booking', 'confirmed', 'checked_in'])
        ]).mapped('room_id').ids
        total_rooms = Room.search_count([])
        today_availability = total_rooms - len(occupied_room_ids)
        total_reservations = Reservation.search_count([])

        kpi = {
            'total_confirmed': total_confirmed,
            'total_checkout': total_checkout,
            'today_availability': today_availability,
            'total_reservations': total_reservations,
        }

        # Rooms grouped by room types
        room_types = []
        for rt in RoomType.search([], order='name'):
            rooms = []
            for room in rt.room_ids.sorted('name'):
                rooms.append({
                    'id': room.id,
                    'name': room.name,
                    'display_name': f"{rt.name} {room.name}",
                })
            room_types.append({
                'id': rt.id,
                'name': rt.name,
                'rooms': rooms,
            })

        # Reservations data for calendar
        reservations = Reservation.search(domain_reservation)
        reservations_data = []
        for resv in reservations:
            # Determine status color code
            status_color = 'gray'
            if resv.status == 'booking':
                status_color = 'blue'
            elif resv.status == 'confirmed':
                status_color = 'darkblue'
            elif resv.status == 'checked_in':
                status_color = 'green'
            elif resv.status == 'checkout':
                status_color = 'orange'
            elif resv.status in ['cleaning', 'maintenance']:
                status_color = 'gray'

            reservations_data.append({
                'id': resv.id,
                'room_id': resv.room_id.id,
                'room_name': resv.room_id.name,
                'room_type': resv.room_id.room_type_id.name,
                'check_in_date': resv.check_in_date.strftime('%Y-%m-%d'),
                'check_out_date': resv.check_out_date.strftime('%Y-%m-%d'),
                'status': resv.status,
                'status_color': status_color,
                'name': resv.name,  # reservation code
                'customer_name': resv.customer_id.name if resv.customer_id else '',
            })

        # Maintenance and cleaning rooms (assumed as separate model or flag on rooms)
        # If those are statuses on rooms, fetch here. For now let's assume room statuses:
        rooms_maintenance_cleaning = Room.search([('status', 'in', ['maintenance', 'cleaning'])])
        maintenance_cleaning_data = []
        for rmc in rooms_maintenance_cleaning:
            maintenance_cleaning_data.append({
                'room_id': rmc.id,
                'status': rmc.status,
                'status_color': 'gray',
            })

        return {
            'kpi': kpi,
            'room_types': room_types,
            'reservations': reservations_data,
            'rooms_maintenance_cleaning': maintenance_cleaning_data,
            'filter_status': filter_status or 'all',
            'start': start,
            'end': end,
        }

    @http.route('/hotel/dashboard/reservation/<int:resv_id>', type='json', auth='user')
    def reservation_form_data(self, resv_id):
        Reservation = request.env['hotel.reservation'].sudo()
        resv = Reservation.browse(resv_id)
        if not resv.exists():
            return {'error': 'Reservation not found'}
        return {
            'id': resv.id,
            'name': resv.name,
            'status': resv.status,
            'check_in_date': resv.check_in_date.strftime('%Y-%m-%d'),
            'check_out_date': resv.check_out_date.strftime('%Y-%m-%d'),
            'customer_name': resv.customer_id.name if resv.customer_id else '',
            'room_id': resv.room_id.id,
            'room_name': resv.room_id.name,
        }

    @http.route('/hotel/dashboard/update_reservation', type='json', auth='user', methods=['POST'])
    def update_reservation(self, **post):
        Reservation = request.env['hotel.reservation'].sudo()
        resv_id = int(post.get('id'))
        resv = Reservation.browse(resv_id)
        if not resv.exists():
            return {'error': 'Reservation not found'}

        try:
            vals = {}
            if 'status' in post:
                vals['status'] = post.get('status')
            if 'check_in_date' in post:
                vals['check_in_date'] = post.get('check_in_date')
            if 'check_out_date' in post:
                vals['check_out_date'] = post.get('check_out_date')
            if 'customer_name' in post and resv.customer_id:
                partner = resv.customer_id
                partner.write({'name': post.get('customer_name')})
            resv.write(vals)
            return {'success': True}
        except AccessError:
            return {'error': 'Access denied'}
        except Exception as e:
            return {'error': str(e)}