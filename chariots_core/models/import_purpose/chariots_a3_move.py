# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)


class ChariotsA3Move(models.Model):

    _name = "chariots.import.a3.move"
    _description = "Chariots: Modelo transicional de los Apuntes Contables de A3"

    number = fields.Integer(string="Nº Apunte")
    move_number = fields.Integer(string="Nº Asiento")
    name = fields.Char(string="Concepto")
    document = fields.Char(string="Documento")
    account_code = fields.Char(string="Nº Cuenta Contable")
    account_desc = fields.Char(string="Descripción de la Cuenta Contable")
    debit = fields.Float(string="Debe")
    credit = fields.Float(string="Haber")
    date = fields.Date(string="Fecha Apunte")
    account_odoo_code = fields.Char(string="Nº Cuenta Contable Odoo")
    analytic_tag_name = fields.Char(string="Nombre de Etiqueta Analítica")
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Compañía",
        related="account_id.company_id"
    )
    account_id = fields.Many2one(
        comodel_name="account.account",
        string="Cuenta Contable"
    )
    partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Empresa"
    )
    analytic_account_id = fields.Many2one(
        comodel_name="account.analytic.account",
        string="Cuenta Analítica"
    )
    move_id = fields.Many2one(
        comodel_name="account.move",
        string="Asiento Contable",
        index=True,
        ondelete="set null"
    )
    line_id = fields.Many2one(
        comodel_name="account.move.line",
        string="Apunte Contable",
        index=True,
        ondelete="set null"
    )
    line_ids = fields.Many2many(
        comodel_name="account.move.line",
        string="Listado de Apuntes Contables"
    )
    is_startup = fields.Boolean(string="Es Startup")
    is_warning = fields.Boolean(string="Hay que Revisarla", default=False)
    is_new = fields.Boolean(string="Creada desde Migración", default=False)
    is_updated = fields.Boolean(string="Código Actualizado", default=False)
    tag_000 = fields.Float(string="000")
    tag_001 = fields.Float(string="001")
    tag_002 = fields.Float(string="002")
    tag_003 = fields.Float(string="003")
    tag_004 = fields.Float(string="004")
    tag_005 = fields.Float(string="005")
    tag_006 = fields.Float(string="006")
    tag_007 = fields.Float(string="007")
    tag_008 = fields.Float(string="008")
    tag_009 = fields.Float(string="009")
    tag_010 = fields.Float(string="010")
    tag_011 = fields.Float(string="011")

    @api.model
    def relate_account(self):
        a3_moves = self.env['chariots.import.a3.move'].search([
            '|', '|',
            ('account_id', '=', False),
            ('account_id.company_id', '!=', 1),
            ('analytic_account_id', '=', False)
        ])
        for a3_move in a3_moves:
            data = {}
            if not a3_move.analytic_account_id:
                analytic_account = self.env['account.analytic.account'].search([
                    ('code', '=', a3_move.analytic_tag_name)
                ], limit=1)
                if analytic_account:
                    data['analytic_account_id'] = analytic_account.id
            if not a3_move.account_id or a3_move.account_id.company_id.id != 1:
                odoo_account = self.env['account.account'].search([
                    ('company_id', '=', 1),
                    '|',
                    ('code', '=', a3_move.account_odoo_code),
                    ('code', '=', "{}-{}".format(a3_move.account_odoo_code[0:4], a3_move.account_odoo_code[4:]))
                ], limit=1)
                if odoo_account:
                    data['account_id'] = odoo_account.id
                    partner = self.env['res.partner'].search([
                        '|',
                        ('property_account_receivable_id', '=', odoo_account.id),
                        ('property_account_payable_id', '=', odoo_account.id),
                    ])
                    if len(partner) == 1:
                        data['partner_id'] = partner[0].id
                else:
                    logging.info("No encuentra la cuenta {}".format(a3_move.account_odoo_code))
                    logging.info("{}-{}".format(a3_move.account_odoo_code[0:4], a3_move.account_odoo_code[4:]))
            if data:
                a3_move.write(data)

            self.env.cr.commit()

    @api.model
    def create_moves(self, date_start='2017-01-01' , date_stop='2017-12-31'):
        a3_moves = self.env['chariots.import.a3.move'].search([
            ('move_id', '=', False),
            ('date', '>=', date_start),
            ('date', '<=', date_stop),
        ])
        moves_created = {}
        for a3_move in a3_moves:
            key = "{}-{}".format(
                a3_move.move_number,
                a3_move.date.year
            )
            if key in moves_created:
                a3_move.write({
                    'move_id': moves_created[key]
                })
                continue
            move_id = self.env['account.move'].create({
                'date': a3_move.date,
                'ref': a3_move.name,
                'name': a3_move.move_number,
                'narration': a3_move.document,
                'journal_id': self.env.ref('chariots_core.analytic_account_journal_migrate').id,
                'partner_id': a3_move.partner_id.id if a3_move.partner_id else False
            })
            if move_id:
                a3_move.write({
                    'move_id': move_id.id,
                    'is_new': True
                })
                moves_created[key] = move_id.id
            else:
                a3_move.write({
                    'is_warning': True
                })

            self.env.cr.commit()

    @api.model
    def create_moves_line(self, date_start='2017-01-01' , date_stop='2017-12-31'):
        a3_moves = self.env['chariots.import.a3.move'].search([
            ('move_id', '!=', False),
            ('account_id', '!=', False),
            ('date', '>=', date_start),
            ('date', '<=', date_stop),
            ('line_id', '=', False),
            ('line_ids', '=', False),
        ], order="date DESC")
        startup_tag = self.env['account.analytic.tag'].search([
            ('name', 'like', 'Startup')
        ], limit=1)
        count = 0
        num_max_line = len(a3_moves)
        for a3_move_line in a3_moves:
            ids = []
            if count >= 150 or num_max_line < 150:
                self.env.cr.commit()
                count = 0
            if a3_move_line.debit + a3_move_line.credit >= 0:
                credit = a3_move_line.credit
                debit = a3_move_line.debit
            else:
                credit = abs(a3_move_line.debit)
                debit = abs(a3_move_line.credit)

            analytic_lines = False
            if a3_move_line.tag_000:
                if a3_move_line.tag_000 >= 0:
                    line_credit = a3_move_line.tag_000
                    line_debit = 0
                else:
                    line_credit = 0
                    line_debit = abs(a3_move_line.tag_000)
                ml = self.env['account.move.line'].create({
                    'account_id': a3_move_line.account_id.id,
                    'ref': a3_move_line.name,
                    'analytic_account_id': self.env.ref('chariots_core.analytic_account_000').id,
                    'name': a3_move_line.number,
                    'debit': line_debit,
                    'credit': line_credit,
                    'date': a3_move_line.date,
                    'narration': a3_move_line.document,
                    'move_id': a3_move_line.move_id.id,
                    'analytic_tag_ids': [(6, 0, [startup_tag.id])] if (startup_tag and a3_move_line.is_startup) else False
                })
                ids.append(ml.id)
                analytic_lines = True
                count += 1
            if a3_move_line.tag_001:
                if a3_move_line.tag_001 >= 0:
                    line_credit = a3_move_line.tag_001
                    line_debit = 0
                else:
                    line_credit = 0
                    line_debit = abs(a3_move_line.tag_001)
                ml = self.env['account.move.line'].create({
                    'account_id': a3_move_line.account_id.id,
                    'ref': a3_move_line.name,
                    'analytic_account_id': self.env.ref('chariots_core.analytic_account_001').id,
                    'name': a3_move_line.number,
                    'debit': line_debit,
                    'credit': line_credit,
                    'date': a3_move_line.date,
                    'narration': a3_move_line.document,
                    'move_id': a3_move_line.move_id.id,
                    'analytic_tag_ids': [(6, 0, [startup_tag.id])] if (startup_tag and a3_move_line.is_startup) else False
                })
                ids.append(ml.id)
                analytic_lines = True
                count += 1
            if a3_move_line.tag_002:
                if a3_move_line.tag_002 >= 0:
                    line_credit = a3_move_line.tag_002
                    line_debit = 0
                else:
                    line_credit = 0
                    line_debit = abs(a3_move_line.tag_002)
                ml = self.env['account.move.line'].create({
                    'account_id': a3_move_line.account_id.id,
                    'ref': a3_move_line.name,
                    'analytic_account_id': self.env.ref('chariots_core.analytic_account_002').id,
                    'name': a3_move_line.number,
                    'debit': line_debit,
                    'credit': line_credit,
                    'date': a3_move_line.date,
                    'narration': a3_move_line.document,
                    'move_id': a3_move_line.move_id.id,
                    'analytic_tag_ids': [(6, 0, [startup_tag.id])] if (startup_tag and a3_move_line.is_startup) else False
                })
                ids.append(ml.id)
                analytic_lines = True
                count += 1
            if a3_move_line.tag_003:
                if a3_move_line.tag_003 >= 0:
                    line_credit = a3_move_line.tag_003
                    line_debit = 0
                else:
                    line_credit = 0
                    line_debit = abs(a3_move_line.tag_003)
                ml = self.env['account.move.line'].create({
                    'account_id': a3_move_line.account_id.id,
                    'ref': a3_move_line.name,
                    'analytic_account_id': self.env.ref('chariots_core.analytic_account_003').id,
                    'name': a3_move_line.number,
                    'debit': line_debit,
                    'credit': line_credit,
                    'date': a3_move_line.date,
                    'narration': a3_move_line.document,
                    'move_id': a3_move_line.move_id.id,
                    'analytic_tag_ids': [(6, 0, [startup_tag.id])] if (startup_tag and a3_move_line.is_startup) else False
                })
                ids.append(ml.id)
                analytic_lines = True
                count += 1
            if a3_move_line.tag_004:
                if a3_move_line.tag_004 >= 0:
                    line_credit = a3_move_line.tag_004
                    line_debit = 0
                else:
                    line_credit = 0
                    line_debit = abs(a3_move_line.tag_004)
                ml = self.env['account.move.line'].create({
                    'account_id': a3_move_line.account_id.id,
                    'ref': a3_move_line.name,
                    'analytic_account_id': self.env.ref('chariots_core.analytic_account_004').id,
                    'name': a3_move_line.number,
                    'debit': line_debit,
                    'credit': line_credit,
                    'date': a3_move_line.date,
                    'narration': a3_move_line.document,
                    'move_id': a3_move_line.move_id.id,
                    'analytic_tag_ids': [(6, 0, [startup_tag.id])] if (startup_tag and a3_move_line.is_startup) else False
                })
                ids.append(ml.id)
                analytic_lines = True
                count += 1
            if a3_move_line.tag_005:
                if a3_move_line.tag_005 >= 0:
                    line_credit = a3_move_line.tag_005
                    line_debit = 0
                else:
                    line_credit = 0
                    line_debit = abs(a3_move_line.tag_005)
                ml = self.env['account.move.line'].create({
                    'account_id': a3_move_line.account_id.id,
                    'ref': a3_move_line.name,
                    'analytic_account_id': self.env.ref('chariots_core.analytic_account_005').id,
                    'name': a3_move_line.number,
                    'debit': line_debit,
                    'credit': line_credit,
                    'date': a3_move_line.date,
                    'narration': a3_move_line.document,
                    'move_id': a3_move_line.move_id.id,
                    'analytic_tag_ids': [(6, 0, [startup_tag.id])] if (startup_tag and a3_move_line.is_startup) else False
                })
                ids.append(ml.id)
                analytic_lines = True
                count += 1
            if a3_move_line.tag_006:
                if a3_move_line.tag_006 >= 0:
                    line_credit = a3_move_line.tag_006
                    line_debit = 0
                else:
                    line_credit = 0
                    line_debit = abs(a3_move_line.tag_006)
                ml = self.env['account.move.line'].create({
                    'account_id': a3_move_line.account_id.id,
                    'ref': a3_move_line.name,
                    'analytic_account_id': self.env.ref('chariots_core.analytic_account_006').id,
                    'name': a3_move_line.number,
                    'debit': line_debit,
                    'credit': line_credit,
                    'date': a3_move_line.date,
                    'narration': a3_move_line.document,
                    'move_id': a3_move_line.move_id.id,
                    'analytic_tag_ids': [(6, 0, [startup_tag.id])] if (startup_tag and a3_move_line.is_startup) else False
                })
                ids.append(ml.id)
                analytic_lines = True
                count += 1
            if a3_move_line.tag_007:
                if a3_move_line.tag_007 >= 0:
                    line_credit = a3_move_line.tag_007
                    line_debit = 0
                else:
                    line_credit = 0
                    line_debit = abs(a3_move_line.tag_007)
                ml = self.env['account.move.line'].create({
                    'account_id': a3_move_line.account_id.id,
                    'ref': a3_move_line.name,
                    'analytic_account_id': self.env.ref('chariots_core.analytic_account_007').id,
                    'name': a3_move_line.number,
                    'debit': line_debit,
                    'credit': line_credit,
                    'date': a3_move_line.date,
                    'narration': a3_move_line.document,
                    'move_id': a3_move_line.move_id.id,
                    'analytic_tag_ids': [(6, 0, [startup_tag.id])] if (startup_tag and a3_move_line.is_startup) else False
                })
                ids.append(ml.id)
                analytic_lines = True
                count += 1
            if a3_move_line.tag_008:
                if a3_move_line.tag_008 >= 0:
                    line_credit = a3_move_line.tag_008
                    line_debit = 0
                else:
                    line_credit = 0
                    line_debit = abs(a3_move_line.tag_008)
                ml = self.env['account.move.line'].create({
                    'account_id': a3_move_line.account_id.id,
                    'ref': a3_move_line.name,
                    'analytic_account_id': self.env.ref('chariots_core.analytic_account_008').id,
                    'name': a3_move_line.number,
                    'debit': line_debit,
                    'credit': line_credit,
                    'date': a3_move_line.date,
                    'narration': a3_move_line.document,
                    'move_id': a3_move_line.move_id.id,
                    'analytic_tag_ids': [(6, 0, [startup_tag.id])] if (startup_tag and a3_move_line.is_startup) else False
                })
                ids.append(ml.id)
                analytic_lines = True
                count += 1
            if a3_move_line.tag_009:
                if a3_move_line.tag_009 >= 0:
                    line_credit = a3_move_line.tag_009
                    line_debit = 0
                else:
                    line_credit = 0
                    line_debit = abs(a3_move_line.tag_009)
                ml = self.env['account.move.line'].create({
                    'account_id': a3_move_line.account_id.id,
                    'ref': a3_move_line.name,
                    'analytic_account_id': self.env.ref('chariots_core.analytic_account_009').id,
                    'name': a3_move_line.number,
                    'debit': line_debit,
                    'credit': line_credit,
                    'date': a3_move_line.date,
                    'narration': a3_move_line.document,
                    'move_id': a3_move_line.move_id.id,
                    'analytic_tag_ids': [(6, 0, [startup_tag.id])] if (startup_tag and a3_move_line.is_startup) else False
                })
                ids.append(ml.id)
                analytic_lines = True
                count += 1
            if a3_move_line.tag_010:
                if a3_move_line.tag_010 >= 0:
                    line_credit = a3_move_line.tag_010
                    line_debit = 0
                else:
                    line_credit = 0
                    line_debit = abs(a3_move_line.tag_010)
                ml = self.env['account.move.line'].create({
                    'account_id': a3_move_line.account_id.id,
                    'ref': a3_move_line.name,
                    'analytic_account_id': self.env.ref('chariots_core.analytic_account_010').id,
                    'name': a3_move_line.number,
                    'debit': line_debit,
                    'credit': line_credit,
                    'date': a3_move_line.date,
                    'narration': a3_move_line.document,
                    'move_id': a3_move_line.move_id.id,
                    'analytic_tag_ids': [(6, 0, [startup_tag.id])] if (startup_tag and a3_move_line.is_startup) else False
                })
                ids.append(ml.id)
                analytic_lines = True
                count += 1
            if a3_move_line.tag_011:
                if a3_move_line.tag_011 >= 0:
                    line_credit = a3_move_line.tag_011
                    line_debit = 0
                else:
                    line_credit = 0
                    line_debit = abs(a3_move_line.tag_011)
                ml = self.env['account.move.line'].create({
                    'account_id': a3_move_line.account_id.id,
                    'ref': a3_move_line.name,
                    'analytic_account_id': self.env.ref('chariots_core.analytic_account_011').id,
                    'name': a3_move_line.number,
                    'debit': line_debit,
                    'credit': line_credit,
                    'date': a3_move_line.date,
                    'narration': a3_move_line.document,
                    'move_id': a3_move_line.move_id.id,
                    'analytic_tag_ids': [(6, 0, [startup_tag.id])] if (startup_tag and a3_move_line.is_startup) else False
                })
                ids.append(ml.id)
                analytic_lines = True
                count += 1
            if not analytic_lines:
                move_line = self.env['account.move.line'].create({
                    'account_id': a3_move_line.account_id.id,
                    'ref': a3_move_line.name,
                    'analytic_account_id': a3_move_line.analytic_account_id.id,
                    'name': a3_move_line.number,
                    'debit': debit,
                    'credit': credit,
                    'date': a3_move_line.date,
                    'narration': a3_move_line.document,
                    'move_id': a3_move_line.move_id.id,
                    'analytic_line_ids': analytic_lines,
                    'analytic_tag_ids': [(6, 0, [startup_tag.id])] if (startup_tag and a3_move_line.is_startup) else False
                })
                if move_line:
                    a3_move_line.write({
                        'line_id': move_line.id
                    })
                else:
                    a3_move_line.write({
                        'is_warning': True
                    })
                count += 1
            else:
                a3_move_line.write({
                    'line_ids': [(6, 0, ids)]
                })

    @api.model
    def publish_moves(self):
        a3_moves = self.env['chariots.import.a3.move'].search([
            ('move_id', '!=', False),
            ('move_id.state', '=', 'draft'),
        ])
        for a3_move in a3_moves:
            a3_move._onchange_line_ids()
            a3_move.action_post()

    def cron_fix_account(self):
        move_lines = self.env['account.move.line'].search([
            ('account_id', 'in', [188, 1158]),
            ('partner_id', '!=', False),
            ('partner_id', '!=', 1847),
        ])
        query = ""
        for line in move_lines:
            query += "UPDATE account_move_line SET account_id = {} WHERE id = {};".format(
                line.partner_id.property_account_payable_id.id,
                line.id
            )
        logging.info(query)
        self._cr.execute(query)