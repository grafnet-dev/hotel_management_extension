from odoo import models, fields
from odoo.exceptions import ValidationError
from odoo import api
from odoo import _




class HotelReservationType(models.Model):
    _name = "hotel.reservation.type"
    _description = "Type de réservation"

    name = fields.Char("Nom du type", required=True)  # Ex: Classique, Day Use, Flexible
    code = fields.Selection(
        [
            ("classic", "Classique (nuitée)"),
            ("day_use", "Day Use"),
            ("flexible", "Flexible"),
        ],
        required=True,
        string="Code",
    )
    
    is_flexible = fields.Boolean(string="Heures flexibles", default=False)
    active = fields.Boolean(default=True)
    description = fields.Text("Description", help="Description du type de réservation")


    @api.model
    def get_reservation_types(self):
        """
        Récupère la liste des types de réservation.
        Utilisable via RPC / API externe.
        :return: dict {success, message, data}
        """
        try:
            types = self.search([])
            data = [{
                "id": t.id,
                "name": t.name,
                "code": t.code,
                "is_flexible": t.is_flexible,
            } for t in types]

            return {
                "success": True,
                "data": data,
                "message": _("Types de réservation récupérés avec succès."),
            }
        except UserError as e:
            return {
                "success": False,
                "message": str(e),
            }
        except Exception as e:
            return {
                "success": False,
                "message": _("Erreur inattendue : %s") % str(e),
            }
            
            
            
            
            