# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import datetime

from odoo import fields, models, api
import calendar
from odoo.exceptions import UserError, ValidationError, Warning
import logging

class WizardMigrateMultiCompany(models.TransientModel):

    _name = 'chariots.wizard.multi.company'
    _description = "Wizard Chariots Multicompañia"


    model_id = fields.Many2one(comodel_name='ir.model', string='Modelo')
    primary_company_id = fields.Many2one(comodel_name='res.company', string='Compañía Principal')
    secondary_company_id = fields.Many2one(comodel_name='res.company', string='Compañía Secundaria')

    
    def button_confirm(self):
        if not self.primary_company_id or not self.secondary_company_id:
            raise UserError("No has metido alguna de las compañias")

        if self.model_id.model:
            self.env[self.model_id.model].duplicate_data(primary_company_id=self.primary_company_id, secondary_company_id=self.secondary_company_id)