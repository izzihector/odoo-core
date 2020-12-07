# -*- coding: utf-8 -*-

import base64
import datetime
import io

import pytz
from odoo import models, fields, api
import logging

from odoo.exceptions import UserError


class CustomReport(models.Model):
    _name = "chariots.report"
    _description = "Reportes Personalizados"

    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string="Nombre",
        required=True,
        copy=True
    )
    from_date = fields.Date(
        string="Desde",
        copy=True,
        required=True
    )
    to_date = fields.Date(
        string="Hasta",
        copy=True,
        required=True
    )
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Compañía",
        copy=True,
        required=True
    )
    template_id = fields.Many2one(
        comodel_name="account.financial.html.report",
        string="Plantilla",
        copy=True,
    )
    analytic_account_ids = fields.Many2many(
        comodel_name="account.analytic.account",
        copy=True,
        string="Cuentas Analíticas"
    )
    analytic_tag_ids = fields.Many2many(
        comodel_name="account.analytic.tag",
        copy=True,
        string="Etiquetas Analíticas"
    )
    period_filter = fields.Selection(
        string="Comparativo basado en",
        selection=[
            ('no_comparison', 'Ninguno'),
            ('previous_period', 'Periodo Previo'),
            ('same_last_year', 'Mismo Periodo Año Pasado')
        ],
        default='no_comparison', required=True
    )
    previous_period = fields.Integer(
        string="Nº de Periodos Previos",
        copy=True,
        default=0
    )
    is_draft_included = fields.Boolean(
        copy=True,
        string="Incluir no asentados"
    )
    is_extended = fields.Boolean(
        copy=True,
        string="Extender todo"
    )
    last_generated_date = fields.Datetime(
        copy=False,
        string="Fecha de generación del fichero"
    )
    last_generated_user = fields.Many2one(
        copy=False,
        comodel_name="res.users",
        string="Usuario que generó el fichero"
    )
    split_by_analytic_ac = fields.Boolean(
        string="Archivos independientes por Cuenta Analítica",
        copy=True,
        default=True
    )
    add_global_report = fields.Boolean(
        string="Añadir Consolidado",
        copy=True,
        default=True
    )
    is_template = fields.Boolean(
        string="Es Base",
        default=True,
        copy=True,
    )
    parent_id = fields.Many2one(
        comodel_name="chariots.report",
        string="Base"
    )
    child_ids = fields.One2many(
        comodel_name="chariots.report",
        string="Reportes",
        inverse_name="parent_id"
    )
    count_childs = fields.Integer(
        string="Nº de Reportes",
        compute="_compute_child"
    )
    report_type = fields.Selection(
        string="Tipo",
        selection=[
            ('account.general.ledger', 'Auditoría Libro Mayor'),
            ('account.financial.html.report', 'Otros Informes'),
        ],
        required=True,
        default="account.financial.html.report"
    )

    @api.multi
    def _compute_child(self):
        for report in self:
            report.count_childs = len(report.child_ids)

    @api.multi
    def action_view_child(self):
        self.ensure_one()
        action = {
            'name': "Reportes",
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'target': 'current',
            'view_mode': 'tree,form',
            'view_type': 'form',
            'domain': [('id', 'in', self.child_ids.ids)]
        }
        return action

    def _create_comparison(self):
        return {
            'filter': self.period_filter,
            'date_from': "",
            'date_to': "",
            'number_period': self.previous_period,
            "periods": [],
            "string": "Sin comparación"
        }

    def get_options(self):
        unfolded = []
        if self.is_extended:
            if self.report_type == 'account.financial.html.report':
                unfolded = self.env['account.financial.html.report.line'].sudo().search([
                    ('children_ids', '=', False),
                    '|', '|', '|',
                    ('financial_report_id', '=', self.template_id.id),
                    ('parent_id.financial_report_id.id', '=', self.template_id.id),
                    ('parent_id.parent_id.financial_report_id.id', '=', self.template_id.id),
                    ('parent_id.parent_id.parent_id.financial_report_id.id', '=', self.template_id.id),
                ]).ids
            else:
                unfolded = ["account_{}".format(ac.id) for ac in self.env['account.account'].sudo().search([
                    ('company_id', '=', self.company_id.id),
                ])]
        options = {
            'all_entries': self.is_draft_included,
            'analytic': True,
            'analytic_account_ids': [{
                'id': ac.id,
                'name': ac.name
            } for ac in self.analytic_account_ids],
            'ir_filters': None,
            'hierarchy': None,
            'partner': None,
            'cash_basis': None,
            'journals': [],
            'analytic_accounts': [ac.id for ac in self.analytic_account_ids],
            'analytic_tags': [at.id for at in self.analytic_tag_ids],
            'date': {
                'date_from': str(self.from_date),
                'date_to': str(self.to_date),
                'filter': 'custom',
                'string': "Reporte desde {} hasta {}".format(
                    str(self.from_date),
                    str(self.to_date)
                )
            },
            'comparison': self._create_comparison(),
            'unfold_all': self.is_extended,
            'unfolded_lines': unfolded,
            'unposted_in_period': True,
            'multi_company': [
                {
                    'id': self.company_id.id,
                    'name': self.company_id.name,
                    'selected': True
                }
            ]
        }
        self.env['account.report']._apply_date_filter(options)
        return options

    @api.model
    def cron_generate_report(self):
        reports = self.env[self._name].with_context(tz="Europe/Madrid").search([
            ('is_template', '=', False),
            ('last_generated_date', '=', False)
        ], limit=5)
        tz = pytz.timezone('Europe/Madrid')
        hoy = datetime.datetime.now()
        hoy_madrid = datetime.datetime.now(tz)
        reports.write({
            'last_generated_date': hoy,
        })
        self.env.cr.commit()
        for report in reports:
            report._generate_report(hoy_madrid)

    @api.multi
    def _generate_report(self, hoy):
        self.ensure_one()
        att_obj = self.env['ir.attachment'].sudo()
        date_str = str(hoy).split('.')[0].replace(':', '.')
        self.write({
            'name': "{} - {}".format(date_str, self.name),
        })
        if self.report_type == 'account.financial.html.report':
            template_id = self.template_id.with_context(lang="es_ES")
            template_name = self.template_id.name
        elif self.report_type == "account.general.ledger":
            template_id = self.env['account.general.ledger'].with_context(lang="es_ES")
            template_name = "Libro Mayor"
        else:
            raise UserError("Es obligatorio elegir un tipo de reporte")

        att_obj.search([
            ('res_model', '=', self._name),
            ('res_id', '=', self.id)
        ]).unlink()
        options = self.get_options()
        if self.split_by_analytic_ac:
            for ac in self.analytic_account_ids:
                response = CustomReportExport()
                options['analytic_account_ids'] = [{
                    'id': ac.id,
                    'name': ac.name
                }]
                options['analytic_accounts'] = [ac.id]
                template_id.get_xlsx(options, response)
                filename = "{} - {}.xlsx".format(template_name, ac.code)
                att_obj.create({
                    'company_id': self.company_id.id,
                    'res_model': self._name,
                    'res_id': self.id,
                    'datas': base64.b64encode(response.output()),
                    'datas_fname': filename,
                    'name': filename,
                })
                self.env.cr.commit()
        else:
            response = CustomReportExport()
            template_id.get_xlsx(options, response)
            filename = "{} - {}.xlsx".format(template_name, "CONSOLIDADO")
            att_obj.create({
                'company_id': self.company_id.id,
                'res_model': self._name,
                'res_id': self.id,
                'datas': base64.b64encode(response.output()),
                'datas_fname': filename,
                'name': filename,
            })
            self.env.cr.commit()
        if self.add_global_report:
            options['analytic_account_ids'] = []
            options['analytic_accounts'] = []
            response = CustomReportExport()
            template_id.get_xlsx(options, response)
            filename = "{} - {}.xlsx".format(template_name, "CONSOLIDADO")
            att_obj.create({
                'company_id': self.company_id.id,
                'res_model': self._name,
                'res_id': self.id,
                'datas': base64.b64encode(response.output()),
                'datas_fname': filename,
                'name': filename,
            })
            self.env.cr.commit()

    @api.multi
    def generate_report(self):
        for report in self:
            if report.is_template:
                report.copy({
                    'name': str(report.name),
                    'is_template': False,
                    'parent_id': report.id,
                    'last_generated_user': self.env.uid
                })
            else:
                raise UserError("No puedes generar un reporte a partir de esta plantilla")


class CustomReportExport():
    stream = None

    def __init__(self):
        self.stream = io.BytesIO()

    def output(self):
        out = self.stream.getvalue()
        self.stream.close()
        return out
