# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class KfcStore(models.Model):

    _name = "chariots.import.kfc.store"
    _description = "Chariots: Modelo transicional de KFC Tiendas"

    external_id = fields.Integer(
        string="ID KFC"
    )

    name = fields.Char(
        string="Nombre"
    )

    analytic_account_id = fields.Many2one(
        comodel_name="account.analytic.account",
        string="Cuenta Analítica"
    )

    partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Cliente para las ventas",
        domain="[('customer','=',True),('sii_simplified_invoice','=',True)]"
    )
