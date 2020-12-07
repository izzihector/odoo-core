# -*- coding: utf-8 -*-

import logging

from odoo import models, fields, api, _


class KfcProduct(models.Model):

    _name = "chariots.import.kfc.product"
    _description = "Chariots: Modelo transicional de KFC Productos"

    _sql_constraints = [
        ('external_id_unique', 'unique(external_id)', 'External ID ya existente.')
    ]

    external_id = fields.Integer(
        string="ID KFC"
    )

    name = fields.Char(
        string="Nombre"
    )

    active = fields.Boolean(
        string="Activo",
        default=True
    )

    short_desc = fields.Text(
        string="Descripción Corta"
    )

    desc = fields.Text(
        string="Descripción"
    )

    category_id = fields.Many2one(
        comodel_name="product.category",
        string="Categoría"
    )

    category_name = fields.Char(
        string="Nombre de Categoría"
    )

    account_name = fields.Char(
        string="Nombre de Cuenta Contable"
    )

    product_id = fields.Many2one(
        comodel_name="product.product",
        string="Producto Odoo"
    )

    account_id = fields.Many2one(
        comodel_name="account.account",
        string="Cuenta del Producto",
        related="product_id.property_account_income_id"
    )

    def relate_account(self):
        kfc_cat_obj = self.env['chariots.import.kfc.category']
        products = self.env[self._name].search([
            ('category_id', '!=', False),
            ('product_id', '=', False),
        ])
        for p in products:
            cat = kfc_cat_obj.search([
                ('category_id', '=', p.category_id.id),
                ('account_id', '=', False),
                ('product_id', '=', False),
            ])
            if cat:
                cat.write({
                    'account_name': p.account_name
                })
                self._cr.commit()

    def relate_models(self):
        kfc_cat_obj = self.env['chariots.import.kfc.category']
        cat_obj = self.env['product.category']
        products = self.env[self._name].search([('category_id', '=', False), ('category_name', '!=', False)])
        for p in products:
            search_cat = kfc_cat_obj.search([('name', 'like', p.category_name)], limit=1)
            if search_cat:
                p.write({
                   'category_id': search_cat.category_id.id if search_cat.category_id else False
                })
                if not search_cat.account_name:
                    search_cat.write({
                        'account_name': p.account_name
                    })
            else:
                cat = cat_obj.create({
                    'name': p.category_name,
                    'parent_id': 4
                })
                kfc_cat_obj.create({
                    'name': p.category_name,
                    'category_id': cat.id,
                    'account_name': p.account_name
                })
            self._cr.commit()

        products = self.env[self._name].search([('product_id', '=', False), ('category_id', '!=', False)])
        for p in products:
            search_product = self.env['product.product'].search([
                ('categ_id', '=', p.category_id.id)
            ], limit=1)
            if search_product:
                p.write({
                    'product_id': search_product.id
                })
            self._cr.commit()
