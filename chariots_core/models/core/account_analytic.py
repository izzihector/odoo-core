# -*- coding: utf-8 -*-
import json
from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError, Warning
import logging
class AccountAnalyticAccount(models.Model):
    _inherit = 'account.analytic.account'

    @api.model
    def duplicate_data(self, primary_company_id, secondary_company_id):
        obj_model = self.env[self._name]
        if primary_company_id and secondary_company_id:
            account_analytics = obj_model.sudo().search([('company_id', '=', primary_company_id.id), ('active', '=', True)])
            if account_analytics:
                for account_analytic in account_analytics:
                    search_account_analytic = obj_model.sudo().search([('code', '=', account_analytic.code), ('company_id', '=', secondary_company_id.id)])
                    if search_account_analytic: 
                        continue
                    dicc = {
                        'company_id': secondary_company_id.id
                    }
                    new_account_analytic = account_analytic.copy(default=dicc)        

