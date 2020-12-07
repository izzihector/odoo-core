# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class ChariotsA3Odoo(models.Model):

    _name = "chariots.import.a3.odoo"
    _description = "Chariots: Modelo transicional de A3 a Odoo"

    a3_code = fields.Char(string="Cuenta A3")
    name = fields.Char(string="Nombre A3")
    analytic_account_name = fields.Char(string="Nombre de Etiqueta Analítica")
    odoo_code = fields.Char(string="Cuenta Odoo")
    odoo_name = fields.Char(string="Nombre Odoo")
    type_es = fields.Char(string="Tipo Español")
    type_en = fields.Char(string="Tipo Inglés")
    tag_description = fields.Char(string="Etiqueta")
    account_id = fields.Many2one(
        comodel_name="account.account",
        string="Cuenta Contable"
    )
    account_type_id = fields.Many2one(
        comodel_name="account.account.type",
        string="Tipo de Cuenta"
    )
    is_warning = fields.Boolean(string="Hay que Revisarla", default=False)
    is_new = fields.Boolean(string="Creada desde Migración", default=False)
    is_updated = fields.Boolean(string="Código Actualizado", default=False)

    @api.model
    def unlink_all(self):
        self.env['chariots.import.a3.odoo'].search([]).unlink()

    @api.model
    def import_to_related(self):
        a3_accounts = self.env['chariots.import.a3.odoo'].search([
            ('account_id', '=', False)
        ])
        for a3_account in a3_accounts:
            key = str(a3_account.odoo_code).replace('-', '')
            account_search = self.env['account.account'].search([
                ('code', '=', key)
            ], limit=1)
            if account_search:
                a3_account.write({
                    'account_id': account_search.id,
                    'account_type_id': account_search.user_type_id.id if account_search.user_type_id else False
                })
                self.env.cr.commit()

        a3_accounts = self.env['chariots.import.a3.odoo'].search([
            ('account_id', '!=', False)
        ])
        for a3_account in a3_accounts:
            key = str(a3_account.odoo_code).replace('-', '')
            if a3_account.account_id.code != key:
                a3_account.write({
                    'account_id': False,
                    'account_type_id': False
                })
                self.env.cr.commit()


    @api.model
    def migrate_accounts(self):
        a3_accounts = self.env['chariots.import.a3.odoo'].search([])
        codes = []
        for a3_account in a3_accounts:
            key = str(a3_account.odoo_code).replace('-', '')
            if key in codes:
                continue
            codes.append(key)
            a3_account.write({
                'is_warning': True
            })
            if not a3_account.account_id:
                ac = self.env['account.account'].search([
                    ('code', '=', key)
                ], limit=1)
                if ac:
                    a3_account.write({
                        'account_id': ac.id,
                        'account_type_id': ac.user_type_id.id if ac.user_type_id else False,
                    })
                else:
                    if a3_account.type_es == 'Amortización':
                        a3_account.type_es = 'Activos fijos'
                    elif a3_account.type_es == 'Pasivos No Corrientes':
                        a3_account.type_es = 'Pasivos no-circulantes'
                    elif a3_account.type_es == 'Pasivo Corriente':
                        a3_account.type_es = 'Pasivo actual'
                    elif a3_account.type_es == 'Activos No Corrientes':
                        a3_account.type_es = 'Activos no-circulantes'
                    elif a3_account.type_es == 'Activos Corrientes':
                        a3_account.type_es = 'Activos actuales'
                    elif a3_account.type_es == 'Otros ingresos':
                        a3_account.type_es = 'Otro ingreso'
                    elif a3_account.type_es == 'Bancos y Caja':
                        a3_account.type_es = 'Banco y Caja'
                    elif a3_account.type_es == 'Coste directo de ventas':
                        a3_account.type_es = 'Coste directo de las ventas'
                    elif a3_account.type_es == 'Otro impuesto':
                        a3_account.type_es = 'Otros tributos'

                    ac_type = self.env['account.account.type'].search([
                        ('name', 'ilike', a3_account.type_es)
                    ], limit=1)
                    ac_group = self.env['account.group'].search([
                        '|',
                        ('code_prefix', '=', key[0:4]),
                        ('code_prefix', '=', key[0:3])
                    ], limit=1)
                    if not ac_type:
                        a3_account.write({
                            'is_warning': True
                        })
                        continue
                    ac = self.env['account.account'].create({
                        'code': key,
                        'name': a3_account.odoo_name,
                        'user_type_id': ac_type.id if ac_type else False,
                        'group_id': ac_group.id if ac_group else False,
                        'reconcile': True if key[0] == '4' else False
                    })
                    a3_account.write({
                        'account_id': ac.id,
                        'account_type_id': ac_type.id if ac_type else False,
                        'is_new': True
                    })
            elif len(a3_account.account_id.code) <= 6:
                a3_account.write({
                    'is_updated': True,
                    'is_warning': False
                })
                a3_account.account_id.write({
                    'code': key
                })
            self.env.cr.commit()


class ChariotsAccountAccount(models.Model):

    _inherit = "account.account"

    @api.multi
    @api.constrains('user_type_id')
    def _check_user_type_id(self):
        pass

