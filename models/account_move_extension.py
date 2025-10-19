import logging
from odoo import models, fields, api

_logger = logging.getLogger(__name__)

class AccountMove(models.Model):
    _inherit = "account.move"

    stay_id = fields.Many2one(
        "hotel.booking.stay",
        string="Séjour",
        ondelete="cascade",
        help="Séjour associé à cette facture"
    )
    
    to_invoice_with_stay = fields.Boolean(
        string="À reporter sur la facture finale",
        default=False,
        help="Si coché, cette facture POS sera incluse dans la facture finale du séjour."
    )
    pos_invoice_reported = fields.Boolean(
        string="Facture POS déjà reprise dans une facture séjour",
        default=False,
        help="Indique si cette facture POS a déjà été incluse dans une facture de séjour.",
    )
    
    @api.model
    def create(self, vals_list):
        """
        Lorsqu'une facture est créée (y compris par le POS),
        on vérifie si elle provient d'une commande POS et si
        un séjour actif existe pour le même client.
        """
        _logger.info("AccountMove create called with vals_list: %s", vals_list)
        
        moves = super(AccountMove, self).create(vals_list)
        _logger.info("Created %d account.move records", len(moves))

        for move in moves:
            _logger.info("Processing move ID %s, type %s, partner %s", move.id, move.move_type, move.partner_id.name)

            # Vérifier que c'est une facture client
            if move.move_type != "out_invoice":
                _logger.info("Skipping move ID %s: not a customer invoice", move.id)
                continue

            # Vérifier si la facture est issue du POS
            pos_order_ids = move.pos_order_ids
            if not pos_order_ids:
                _logger.info("Move ID %s has no POS order linked", move.id)
                continue
            _logger.info("Move ID %s linked to POS orders: %s", move.id, pos_order_ids.ids)

            # Chercher un séjour en cours pour ce client
            stay = self.env["hotel.booking.stay"].search([
                ("occupant_ids", "in", move.partner_id.id),  # <--- adapte ici
                ("state", "=", "ongoing"),
            ], limit=1)


            if stay:
                move.stay_id = stay.id
                move.to_invoice_with_stay = True
                _logger.info("Move ID %s linked to stay ID %s", move.id, stay.id)
            else:
                _logger.info("No ongoing stay found for partner %s", move.partner_id.name)

        return moves
