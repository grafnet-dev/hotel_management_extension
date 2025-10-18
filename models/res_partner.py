from odoo import models, fields

class ResPartner(models.Model):
    _inherit = 'res.partner'

    id_number = fields.Char("Numéro d'identité")

    def name_get(self):
        result = []
        for record in self:
            display_name = record.name or ''
            if record.phone:
                display_name += f" — 📞 {record.phone}"
            if record.id_number:
                display_name += f" — 🪪 {record.id_number}"
            result.append((record.id, display_name))
        return result
