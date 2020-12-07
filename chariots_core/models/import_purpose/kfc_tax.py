# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class KfcTax(models.Model):

    _name = "chariots.import.kfc.tax"
    _description = "Chariots: Modelo transicional de KFC Impuestos"

    external_id = fields.Integer(
        string="ID KFC"
    )
    name = fields.Char(
        string="Nombre"
    )

    tax_id = fields.Many2one(
        comodel_name="account.tax",
        string="Impuesto Odoo"
    )

