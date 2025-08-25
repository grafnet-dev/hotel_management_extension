from odoo.http import request, route, Controller
import odoo
import logging

# `Configurer le logger`

_logger = logging.getLogger(__name__)

class ReceptionAppController(Controller):
    @route("/hotel/reception", auth="public")
    def reception_app(self):
        # Créer manuellement les informations de session sans get_frontend_session_info()
        user = request.env.user

        # Informations de session basiques
        session_info = {
            'uid': user.id,
            'is_admin': user.has_group('base.group_erp_manager'),
            'is_system': user.has_group('base.group_system'),
            'user_name': user.name,
            'username': user.login,
            'user_context': dict(request.env.context),
            'db': request.env.cr.dbname,
            'server_version': odoo.release.version,  # Version correcte
            'server_version_info': odoo.release.version_info,
        }

        # Logging des informations récupérées
        _logger.info("=== SESSION INFO SANS website=True ===")
        _logger.info(f"Session info keys: {list(session_info.keys())}")
        _logger.info(f"UID: {session_info.get('uid')}")
        _logger.info(f"User name: {session_info.get('user_name')}")
        _logger.info(f"Username: {session_info.get('username')}")
        _logger.info(f"Is admin: {session_info.get('is_admin')}")
        _logger.info(f"Is system: {session_info.get('is_system')}")
        _logger.info(f"Database: {session_info.get('db')}")
        _logger.info(f"Server version: {session_info.get('server_version')}")
        _logger.info(f"User context: {session_info.get('user_context')}")
        _logger.info("=== FIN SESSION INFO ===")

        # Ajouter des informations supplémentaires si nécessaire
        context = {
            'session_info': session_info,
        }
        # Vérifier si les templates sont chargés
        try:
            template_exists = request.env.ref('hotel_management_extension.reception_standalone_app')
            _logger.info(f"Template trouvé: {template_exists}")
        except Exception as e:
            _logger.error(f"Erreur template: {e}")


        return request.render(
            'hotel_management_extension.reception_standalone_app',
            context
        )

