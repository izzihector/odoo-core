# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)


class ChariotsImportProduct(models.Model):

    _name = "chariots.import.product"
    _description = "Chariots: Modelo transicional de los productos"

    account = fields.Char(string="Cuenta Proveedor")
    partner_desc = fields.Char(string="Nombre Proveedor")
    partner_nif = fields.Char(string="NIF Proveedor")
    name = fields.Char(string="Nombre Producto")
    odoo_account = fields.Char(string="Cuenta Odoo")
    partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Proveedor"
    )
    partner_ac_id = fields.Many2one(
        comodel_name="account.account",
        string="Cuenta de Proveedor"
    )
    product_id = fields.Many2one(
        comodel_name="product.product",
        string="Producto"
    )
    product_ac_id = fields.Many2one(
        comodel_name="account.account",
        string="Cuenta de Producto"
    )
    type = fields.Char(
        string="Tipo"
    )
    tag = fields.Char(
        string="Etiqueta Analítica"
    )
    iva1 = fields.Char(
        string="IVA - 1"
    )
    iva2 = fields.Char(
        string="IVA - 2"
    )
    iva3 = fields.Char(
        string="IVA - 3"
    )
    is_warning = fields.Boolean(
        string="A Revisar",
        default=False
    )

    @api.model
    def find_relational(self):
        import_products = self.env[self._name].search([])
        for product_imp in import_products:
            data = {}
            search_product_ac = self.env['account.account'].search([
                ('code', '=', str(product_imp.odoo_account).replace('-', '')),
            ], limit=1)
            if search_product_ac:
                data['product_ac_id'] = search_product_ac.id

            ivas_raw = []
            if product_imp.iva1:
                ivas_raw.append(product_imp.iva1)
            if product_imp.iva2:
                ivas_raw.append(product_imp.iva2)
            if product_imp.iva3:
                ivas_raw.append(product_imp.iva3)
            ivas = []
            for iva in ivas_raw:
                if iva.find('10') > -1:
                    if product_imp.type == 'Servicio':
                        ivas.append(43)
                    else:
                        ivas.append(41)
                elif iva.find('21') > -1:
                    if product_imp.type == 'Servicio':
                        ivas.append(5)
                    else:
                        ivas.append(4)
                elif iva.find('4') > -1:
                    if product_imp.type == 'Servicio':
                        ivas.append(38)
                    else:
                        ivas.append(42)
                elif iva.find('0') > -1:
                    if product_imp.type == 'Servicio':
                        ivas.append(54)
                    else:
                        ivas.append(55)

            if not product_imp.product_id:
                search_product = self.env['product.product'].search([
                    ('name', 'like', product_imp.name)
                ], limit=1)
                if search_product:
                    product = search_product
                    product_imp.supplier_taxes_ids = [(6, 0, ivas)]
                else:
                    product = self.env['product.product'].create({
                        'name': product_imp.name,
                        'sale_ok': True if search_product_ac and str(product_imp.odoo_account)[0] == '7' else False,
                        'purchase_ok': True if search_product_ac and str(product_imp.odoo_account)[0] == '6' else False,
                        'property_account_income_id': search_product_ac.id if search_product_ac and str(product_imp.odoo_account)[0] == '7' else False,
                        'property_account_expense_id': search_product_ac.id if search_product_ac and str(product_imp.odoo_account)[0] == '6' else False,
                        'supplier_taxes_id': [(6, 0, ivas)],
                        'type': 'service' if product_imp.type == 'Servicio' else 'consu'
                    })
                if product:
                    data['product_id'] = product.id

            if data:
                product_imp.update(data)

            self.env.cr.commit()

    def set_accounts(self, force=False):
        import_products = self.env[self._name].search([])
        for product_imp in import_products:
            is_change = False
            if product_imp.partner_ac_id and ((product_imp.partner_id and not product_imp.partner_id.property_account_payable_id) or (product_imp.partner_id and force)):
                product_imp.partner_id.update({
                    'property_account_payable_id': product_imp.partner_ac_id.id
                })
                is_change = True
            if product_imp.product_ac_id and ((product_imp.product_id and not product_imp.product_id.property_account_expense_id) or (product_imp.product_id and force)):
                product_imp.product_id.update({
                    'property_account_expense_id': product_imp.product_ac_id.id
                })
                is_change = True
            if is_change:
                self.env.cr.commit()
