# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class KfcPayMethod(models.Model):

    _name = "chariots.import.kfc.paymethod"
    _description = "Chariots: Modelo transicional de KFC Métodos de Pago"

    external_id = fields.Integer(
        string="ID KFC"
    )
    name = fields.Char(
        string="Nombre"
    )
    account_id = fields.Many2one(
        string="Cuenta Contable",
        comodel_name="account.account"
    )
    journal_id = fields.Many2one(
        string="Diario",
        comodel_name="account.journal"
    )


