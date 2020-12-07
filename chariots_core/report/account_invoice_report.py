
from odoo import fields, models


class AccountInvoiceReport(models.Model):

    _inherit = "account.invoice.report"

    real_sale_date = fields.Date(string="Fecha de Venta Real")
    # percent_tax_id = fields.Float(string='IVA %', readonly=True)
    amount_tax = fields.Float(string='Total IVA', readonly=True)

    def _select(self):
        return super(AccountInvoiceReport, self)._select() + ", sub.real_sale_date as real_sale_date, sub.amount_tax as amount_tax"

    def _sub_select(self):
        return super(AccountInvoiceReport, self)._sub_select() + ", ai.real_sale_date as real_sale_date, ((acc_inv_tax.amount / 100) * (SUM(ail.price_subtotal_signed * invoice_type.sign))) as amount_tax"
    
    def _group_by(self):
        return super(AccountInvoiceReport, self)._group_by() + ", acc_inv_tax.id"
    
    def _from(self):
        return super(AccountInvoiceReport, self)._from() + """
            LEFT JOIN account_invoice_line_tax acc_inv_l_tax ON acc_inv_l_tax.invoice_line_id = ail.id
            LEFT JOIN account_tax acc_inv_tax ON acc_inv_tax.id = acc_inv_l_tax.tax_id
            LEFT JOIN LATERAL  (
            SELECT product_supplierinfo.*
            FROM product_supplierinfo
            WHERE product_tmpl_id = pt.id
            LIMIT 1 
        ) AS supplier ON supplier.product_tmpl_id = pt.id"""