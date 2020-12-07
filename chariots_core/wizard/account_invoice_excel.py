# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import datetime

from odoo import fields, models, api
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT
import logging
import calendar
from datetime import datetime


class AccountInvoiceExcel(models.TransientModel):

    _name = 'chariots.account.invoice.excel'
    _description = "Wizard Chariots: Exportar Facturas a Excel"

    type = fields.Selection(selection=[
        ('customer', 'Clientes'),
        ('supplier', 'Proveedores'),
    ], string="Libro de:")
    supplier_ids = fields.Many2many(
        comodel_name='res.partner',
        string='Proveedores',
        domain=[('supplier', '=', True), ('parent_id', '=', False)]
    )
    customer_ids = fields.Many2many(
        comodel_name='res.partner',
        string='Clientes',
        domain=[('customer', '=', True), ('parent_id', '=', False)]
    )
    
    @api.model
    def _get_default_initial_date(self):
        date_now = datetime.now()
        actual_month = date_now.month
        if actual_month == 0:
            before_month = 11
            before_year = date_now.year -1
        else:
            before_month = actual_month -1
            before_year = date_now.year
        
        initial_time_datetime = datetime(year=before_year, month=before_month, day=1)
        return initial_time_datetime.date()
    
    @api.model
    def _get_default_end_date(self):
        date_now = datetime.now()
        actual_month = date_now.month
        if actual_month == 0:
            before_month = 11
            before_year = date_now.year -1
        else:
            before_month = actual_month -1
            before_year = date_now.year
        
        day_month_end = calendar.monthrange(before_year, before_month)[1]
        end_time_datetime = datetime(year=before_year, month=before_month, day=day_month_end)
        
        return end_time_datetime.date()
    
    initial_date = fields.Date(string='Fecha Inicio', default=_get_default_initial_date, required=True)
    end_date = fields.Date(string='Fecha Fin', default=_get_default_end_date, required=True)

    @api.onchange('initial_date', 'end_date')
    def _onchange_dates(self):
        actual_month = self.initial_date.month
        actual_year = self.initial_date.year
        day_month_end = calendar.monthrange(actual_year, actual_month)[1]
        end_time_datetime = datetime(year=actual_year, month=actual_month, day=day_month_end)
        self.end_date = end_time_datetime.date()