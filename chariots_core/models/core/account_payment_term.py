# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class AccountPaymentTerm(models.Model):
    _inherit = "account.payment.term"

    @api.model
    def duplicate_data(self, primary_company_id, secondary_company_id):
        obj_model = self.env[self._name]
        if primary_company_id and secondary_company_id:
            terms = obj_model.sudo().search([('company_id', '=', primary_company_id.id)])
            if terms:
                for term in terms:
                    search_term = obj_model.sudo().search([('name', 'ilike', term.name), ('company_id', '=', secondary_company_id.id)])
                    if search_term: 
                        continue
                    
                    dicc = {
                        'company_id': secondary_company_id.id,
                    }
                    new_term = term.copy(default=dicc)
                    new_term.write({'name': term.name})
                   