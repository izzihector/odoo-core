# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class KfcTimeRange(models.Model):

    _name = "chariots.import.kfc.timerange"
    _description = "Chariots: KFC - Rango de tiempo"

    name = fields.Char(
        string="Nombre"
    )

    start_hour = fields.Float(
        string="Hora Inicio"
    )

    end_hour = fields.Float(
        string="Hora Fin"
    )

    analytic_tag_id = fields.Many2one(
        comodel_name="account.analytic.tag",
        string="Etiqueta analítica"
    )

    order = fields.Integer(
        string="Orden"
    )