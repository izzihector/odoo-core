# -*- coding: utf-8 -*-

from odoo import api, fields, models, _

class IrSequence(models.Model):
    _inherit = 'ir.sequence'

    @api.model
    def duplicate_data(self, primary_company_id, secondary_company_id):
        obj_model = self.env[self._name]
        if primary_company_id and secondary_company_id:
            sequences = obj_model.sudo().search([('company_id', '=', primary_company_id.id)])
            if sequences:
                for sequence in sequences:
                    search_sequence = obj_model.sudo().search([('name', 'ilike', sequence.name), ('company_id', '=', secondary_company_id.id)])
                    if search_sequence: 
                        continue

                    dicc = {
                        'company_id': secondary_company_id.id,
                    }
                    new_sequence = sequence.copy(default=dicc)

