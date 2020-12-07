# -*- coding: utf-8 -*-

from odoo import api, fields, models, _

class HrEmployee(models.Model):
    _inherit = "hr.employee"

    def_acc_analytic_id = fields.Many2one(string='Cuenta Analítica por Defecto', comodel_name='account.analytic.account')
    