# -*- coding: utf-8 -*-

from odoo import models, fields, api

class AccountFiscalPosition(models.Model):
    _inherit = "account.fiscal.position"

    @api.model
    def duplicate_data(self, primary_company_id, secondary_company_id):
        obj_model = self.env[self._name]
        account_tax_obj = self.env['account.tax']
        if primary_company_id and secondary_company_id:
            positions = obj_model.sudo().search([('company_id', '=', primary_company_id.id)])
            if positions:
                for position in positions:
                    search_position = obj_model.sudo().search([('name', 'ilike', position.name), ('company_id', '=', secondary_company_id.id)])
                    if search_position: 
                        continue
                    
                    dicc = {
                        'company_id': secondary_company_id.id,
                    }
                    new_position = position.copy(default=dicc)
                    new_position.write({'name': position.name})
                    if new_position.tax_ids:
                        for tax in new_position.tax_ids:
                            tax_src_id = tax.tax_src_id
                            search_tax_src = account_tax_obj.sudo().search([('description', '=', tax_src_id.description), ('company_id', '=', secondary_company_id.id)])
                            if search_tax_src:
                                tax_src_id = search_tax_src
                                tax.write({'tax_src_id': tax_src_id.id}) 
                            tax_dest_id = tax.tax_dest_id
                            search_tax_dest = account_tax_obj.sudo().search([('description', '=', tax_dest_id.description), ('company_id', '=', secondary_company_id.id)])
                            if search_tax_dest:
                                tax_dest_id = search_tax_dest
                                tax.write({'tax_dest_id': tax_dest_id.id}) 
                            