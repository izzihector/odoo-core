# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class KfcChannel(models.Model):

    _name = "chariots.import.kfc.channel"
    _description = "Chariots: Modelo transicional de KFC Canal de Venta"

    external_id = fields.Integer(
        string="ID KFC"
    )
    name = fields.Char(
        string="Nombre"
    )
    analytic_tag_id = fields.Many2one(
        comodel_name="account.analytic.tag",
        string="Etiqueta analítica"
    )
    account_id = fields.Many2one(
        string="Cuenta Contable",
        comodel_name="account.account"
    )
