# -*- coding: utf-8 -*-
{
    'name': "hotel_management_extension",

    'summary': "Short (1 phrase/line) summary of the module's purpose",

    'description': """
Long description of module's purpose
    """,

    'author': "My Company",
    'website': "https://www.yourcompany.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/15.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Uncategorized',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['hotel_management_odoo'],
     
    'assets': {
        'web.assets_backend': [
            'hotel_management_extension/static/src/js/time_clock_widget.js',
            'hotel_management_extension/static/src/xml/time_clock_template.xml',
            'hotel_management_extension/static/src/js/time_float_widget.js',
            'hotel_management_extension/static/src/xml/time_float_template.xml',
        ],
    },


    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'views/hotel_room_type_views.xml',
        'views/hotel_room_views.xml',
        'views/hotel_room_reservation_slot_views.xml',
        'views/hotel_room_pricing_views.xml',
        'views/room_booking_views.xml',
        'views/hotel_police_views.xml',
        'views/hotel_booking_stays.xml',
        'views/views.xml',
        'views/templates.xml',  
        
        
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
}

