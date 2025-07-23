# -*- coding: utf-8 -*-
{
    "name": "hotel_management_extension",
    "summary": "Short (1 phrase/line) summary of the module's purpose",
    "description": """
        Long description of module's purpose
    """,
    "author": "My Company",
    "website": "https://www.yourcompany.com",
    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/15.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    "category": "Uncategorized",
    "version": "0.1",
    # any module necessary for this one to work correctly
    "depends": ["hotel_management_odoo", "base", "web", "website"],
    "assets": {
        "web.assets_backend": [
            "hotel_management_extension/static/src/styles/room_list.css",
            "hotel_management_extension/static/src/js/test_debug.js",  # AJOUTE CETTE LIGNE
            "hotel_management_extension/static/src/xml/test_debug.xml",  # AJOUTE CETTE LIGNE
            "hotel_management_extension/static/src/js/hotel_ui_app.js",
            "hotel_management_extension/static/src/xml/hotel_ui_template.xml",
            "hotel_management_extension/static/src/js/hotel_ui_app.js",
            "hotel_management_extension/static/src/xml/hotel_ui_template.xml",
            "hotel_management_extension/static/src/js/test_simple.js",
            "hotel_management_extension/static/src/js/time_clock_widget.js",
            "hotel_management_extension/static/src/xml/time_clock_template.xml",
            "hotel_management_extension/static/src/js/time_float_widget.js",
            "hotel_management_extension/static/src/xml/time_float_template.xml",
        ],
        "hotel_management_extension.assets_reception_standalone_app": [
            # Assets de base d'Odoo
            # ORDRE IMPORTANT : Assets de base d'Odoo d'abord
            ("include", "web._assets_helpers"),
            ("include", "web._assets_core"),
            ("include", "web.assets_common"),  # OWL, utils, etc.
            ("include", "web.assets_backend_helpers"),
            "hotel_management_extension/static/src/reception_standalone_app/**/*",
            # JS
            # XML
            # CSS (si besoin)
        ],
    },
    # always loaded
    "data": [
        "security/ir.model.access.csv",
        "views/hotel_room_views.xml",
        "views/hotel_room_reservation_slot_views.xml",
        "views/hotel_room_pricing_views.xml",
        "views/room_booking_views.xml",
        "views/hotel_police_views.xml",
        "views/product_template_views.xml",
        "views/hotel_ui_menu.xml",  # menu + action UI juste pour le test
        "views/reception_standalone_app_template.xml",
        "views/room_menu.xml",
        "views/views.xml",
        "views/templates.xml",
    ],
    # only loaded in demonstration mode
    "demo": [
        "demo/demo.xml",
    ],
}
