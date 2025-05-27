from datetime import datetime, timedelta, time
from odoo import api, SUPERUSER_ID

def convert_float_to_datetime(env):
    """
    Convertit les champs Float horaires en Datetime en gardant la date d'aujourd'hui
    Exemple : 14.5 (14h30) -> 2025-05-23T14:30:00
    """

    Room = env['hotel.room'].sudo()

    rooms = Room.search([])
    today = datetime.today().date()

    for room in rooms:
        # Pour chaque champ float, on convertit en datetime en gardant la date du jour

        def float_to_datetime(float_hour):
            if float_hour is None:
                return None
            hours = int(float_hour)
            minutes = int(round((float_hour - hours) * 60))
            return datetime.combine(today, time(hours, minutes))

        # Lire les valeurs float actuelles
        default_check_in_float = room.default_check_in_time if isinstance(room.default_check_in_time, float) else None
        default_check_out_float = room.default_check_out_time if isinstance(room.default_check_out_time, float) else None
        day_use_check_in_float = room.day_use_check_in if isinstance(room.day_use_check_in, float) else None
        day_use_check_out_float = room.day_use_check_out if isinstance(room.day_use_check_out, float) else None

        vals = {}

        if default_check_in_float is not None:
            vals['default_check_in_time'] = float_to_datetime(default_check_in_float)
        if default_check_out_float is not None:
            vals['default_check_out_time'] = float_to_datetime(default_check_out_float)
        if day_use_check_in_float is not None:
            vals['day_use_check_in'] = float_to_datetime(day_use_check_in_float)
        if day_use_check_out_float is not None:
            vals['day_use_check_out'] = float_to_datetime(day_use_check_out_float)

        if vals:
            room.write(vals)
