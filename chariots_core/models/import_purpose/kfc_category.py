# -*- coding: utf-8 -*-

import logging

from odoo import models, fields, api, _


class KfcCategory(models.Model):

    _name = "chariots.import.kfc.category"
    _description = "Chariots: Modelo transicional de KFC Categorías"

    external_id = fields.Integer(
        string="ID KFC"
    )

    name = fields.Char(
        string="Nombre"
    )

    category_id = fields.Many2one(
        comodel_name="product.category",
        string="Categoría"
    )

    account_id = fields.Many2one(
        comodel_name="account.account",
        string="Cuenta"
    )

    account_name = fields.Char(
        string="Nombre de Cuenta"
    )

    product_id = fields.Many2one(
        comodel_name="product.product",
        string="Producto"
    )

    def set_categories(self):
        account_obj = self.env['account.account']
        categories = self.env[self._name].search([('category_id', '=', False)])
        for category in categories:
            parent_cat = self.env['product.category'].search([
                ('name', 'ilike', 'kfc')
            ], limit=1)
            cat = self.env['product.category'].create({
                'name': "{}".format(category.name),
                'parent_id': parent_cat.id if parent_cat else False
            })
            category.write({
                'category_id': cat.id
            })
            self.env.cr.commit()

        categories = self.env[self._name].search([
            ('category_id', '!=', False),
            ('account_name', '!=', False),
            ('account_id', '=', False)
        ])
        for category in categories:
            search_account = account_obj.search([
                ('name', 'ilike', "Ventas - {}".format(category.account_name))
            ], limit=1)
            if search_account:
                category.write({
                    'account_id': search_account.id
                })
                self._cr.commit()
            else:
                logging.info("No se encuentra: {}".format(category.account_name))

    def create_products(self):
        categories = self.env[self._name].search([
            ('category_id', '!=', False),
            ('account_id', '!=', False),
        ])
        for cat in categories:
            data = {
                'name': "KFC - {}".format(cat.name),
                'categ_id': cat.category_id.id,
                'type': 'consu',
                'sale_ok': True,
                'purchase_ok': False,
                'taxes_id': [(6, 0, [47])],
                'company_id': False,
                'property_account_income_id': cat.account_id.id
            }
            cat.category_id.write({
                'property_account_income_categ_id': cat.account_id.id
            })
            if cat.product_id:
                cat.product_id.write(data)
            else:
                p = self.env['product.product'].create(data)
                cat.write({
                    'product_id': p.id
                })
            self.env.cr.commit()

