# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
import logging

class ResPartner(models.Model):
    _name = 'res.partner'
    _inherit = 'res.partner'

    state_name = fields.Char(string="Nombre de Provincia")
    country_name = fields.Char(string="Nombre de País")
    provide_for = fields.Char(string="Restaurante al que provee")
    accounting_name = fields.Char(string="ACCOUNTING (pdte. definir)")
    type_of_service = fields.Char(string="Tipo de Servicio")
    detailed_service = fields.Char(string="Servicio Detallado")
    invoice_format = fields.Char(string="Formato de Factura")
    payment_origin = fields.Char(string="Vía de Pag.")
    payment_origin_sel = fields.Selection(
        string="Vía de Pago", 
        selection=[
            ('direct_debit','Direct Debit'),
            ('bank_transfer','Bank Transfer')
        ]
    )
    payment_interval = fields.Char(string="Vencimiento de Pago")
    bank_account_names = fields.Char(string="Cuentas de Banco")
    payment_frequency = fields.Char(string="Frecuencia de Pago")
    a3_name = fields.Char(string="Nombre en A3")
    a3_account = fields.Char(string="Cuenta en A3")
    display_name = fields.Char(compute='_compute_display_name')
    ref = fields.Char(required=True)
    sii_description_method = fields.Selection(
        selection=[
            ('first_line', 'Primera Línea'),
            ('custom', ' Personalizada')
        ],
        string="Método descripción SII",
        help='Para saber el tipo de descripcion del SII que aparecera en las facturas'
    )
    custom_description_sii = fields.Text(
        string='Descripción personalizada SII',
        help='Si es personalizado aparecera este valor en la descripcion del SII de las facturas'
    )

    @api.depends('ref')
    def _compute_display_name(self):
        super(ResPartner, self)._compute_display_name()

    @api.multi
    def name_get(self):
        result = []
        origin = super(ResPartner, self).name_get()
        orig_name = dict(origin)
        for partner in self:
            name = "{} {}".format(" ({}) ".format(partner.ref) if partner.ref else "", orig_name[partner.id])
            result.append((partner.id, name))
        return result

    @api.onchange('ref', 'name')
    def _onchange_display_name(self):
        self._compute_display_name()

    @api.model
    def cron_same_code_account_in_all_companies(self):
        partners = self.env[self._name].search([])
        updates = []
        for p in partners:
            updates.append({
                'partner_id': p.id,
                'account_receivable_code': p.property_account_receivable_id.code,
                'account_payable_code': p.property_account_payable_id.code
            })
        for val in updates:
            ac_rec = self.env['account.account'].with_context(force_company=2, company_id=2).search([
                ('code', '=', val['account_receivable_code'])
            ], limit=1)
            ac_pay = self.env['account.account'].with_context(force_company=2, company_id=2).search([
                ('code', '=', val['account_payable_code'])
            ], limit=1)
            if not ac_rec or not ac_pay or ac_rec.company_id.id != 2 or ac_pay.company_id.id != 2:
                logging.info(val)
                continue
            self.env[self._name].with_context(force_company=2, company_id=2).browse(int(val['partner_id'])).write({
                'property_account_receivable_id': ac_rec.id,
                'property_account_payable_id': ac_pay.id,
            })