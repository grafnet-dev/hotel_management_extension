from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from ..constants.booking_stays_state import BOOKING_STATES

class RoomBooking(models.Model):
    _inherit = 'room.booking'
    
    stay_ids = fields.One2many(
        'hotel.booking.stay',  
        'booking_id',
        string="Séjours",
        help="Séjours individuels liés à cette réservation"
    )
    
    pricelist_id = fields.Many2one(
        comodel_name='product.pricelist',
        string="Pricelist",
        required=False,

    )
    state_new = fields.Selection(
        selection=[
            (BOOKING_STATES["DRAFT"], "Brouillon"),
            (BOOKING_STATES["CONFIRMED"], "Confirmé"),
            (BOOKING_STATES["ONGOING"], "En cours"),
            (BOOKING_STATES["COMPLETED"], "Terminé"),
            (BOOKING_STATES["CANCELLED"], "Annulé"),
        ],
        compute="_compute_state_new",
        store=True,
    )
    
    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('room.booking.custom')
        return super().create(vals)
    
    @api.depends("state")
    def _compute_state_new(self):
        mapping = {
            "draft": BOOKING_STATES["DRAFT"],
            "reserved": BOOKING_STATES["CONFIRMED"],
            "check_in": BOOKING_STATES["ONGOING"],
            "check_out": BOOKING_STATES["COMPLETED"], # ou peut-être "ongoing" selon la logique métier
            "done": BOOKING_STATES["COMPLETED"],
            "cancel": BOOKING_STATES["CANCELLED"],
        }
        for rec in self:
            rec.state_new = mapping.get(rec.state, BOOKING_STATES["DRAFT"])
    


    def action_start_checkin_wizard(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Fiche de Police',
            'res_model': 'hotel.police.form',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_booking_id': self.id,
                'default_stay_id': self.id,
            }
        }

    def action_view_booking_stays(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Séjours liés',
            'res_model': 'hotel.booking.stay',
            'view_mode': 'list,form',
            'domain': [('booking_id', '=', self.id)],
            'context': {'default_booking_id': self.id},
        }

    @api.model
    def create_booking(self, vals):
        """
        Crée une réservation depuis une application externe via RPC.
        :param vals: dict contenant les champs du booking et ses lignes
        :return: dict {success, id, message}
        """
        try:
            # --- Vérifications des champs obligatoires ---
            required_fields = ['partner_id']
            for field in required_fields:
                if field not in vals or not vals[field]:
                    raise ValidationError(_("Le champ '%s' est obligatoire.") % field)

            # --- Création de la réservation ---
            booking = self.create(vals)

            return {
                "success": True,
                "message": _("Réservation créée avec succès."),
                "data": {
                    "id": booking.id,
                    "state": booking.state,
                    "partner_id": booking.partner_id.id,
                    "partner_name": booking.partner_id.name,
                },
            }

        except ValidationError as e:
            return {
                "success": False,
                "message": str(e),
            }
        except UserError as e:
            return {
                "success": False,
                "message": str(e),
            }
        except Exception as e:
            # Catch générique si autre erreur inattendue
            return {
                "success": False,
                "message": _("Erreur interne : %s") % str(e),
            }
    
    