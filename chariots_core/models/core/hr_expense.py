# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import float_compare

class HrExpenseSheet(models.Model):
    _inherit = "hr.expense.sheet"

    """@api.model
    def _default_journal_id(self):
        journal = self.env.ref('hr_expense.hr_expense_account_journal', raise_if_not_found=False)
        if not journal:
            journal = self.env['account.journal'].search([('type', '=', 'purchase'), ('code', '=', 'FREM')], limit=1)
        return journal.id"""


    @api.multi
    def action_sheet_move_create(self):
        expense_line_ids = \
            self.mapped('expense_line_ids').filtered('invoice_id')
        if expense_line_ids:
            for line in expense_line_ids:
                if line.invoice_id.state in ['draft','cancel']:
                    raise UserError(_('La factura {} aún no esta validada'.format(line.invoice_id.ref)))
        return super(HrExpenseSheet, self).action_sheet_move_create()
    
    @api.model
    def _validate_expense_invoice(self, expense_lines):
        DecimalPrecision = self.env['decimal.precision']
        precision = DecimalPrecision.precision_get('Product Price')
        invoices = expense_lines.mapped('invoice_id')
        if not invoices:
            return
        # All invoices must confirmed
        if any(invoices.filtered(lambda i: i.state != 'open')):
            pass
        expense_amount = sum(expense_lines.mapped('total_amount'))
        invoice_amount = sum(invoices.mapped('residual'))
        # Expense amount must equal invoice amount
        if float_compare(expense_amount, invoice_amount, precision) != 0:
            raise UserError(
                _('Vendor bill amount mismatch!\nPlease make sure amount in '
                  'vendor bills equal to amount of its expense lines'))


class HrExpense(models.Model):
    _inherit = "hr.expense"

    product_id = fields.Many2one(required=False)
    product_uom_id = fields.Many2one(required=False)

    invoice_id = fields.Many2one(
        domain="[('type', '=', 'in_invoice')]",
        oldname=''
    )

    @api.constrains('invoice_id')
    def _check_invoice_id(self):
        for expense in self:  # Only non binding expense
            if not expense.sheet_id and expense.invoice_id and \
                    expense.invoice_id.state != 'open':
                pass
    
    @api.multi
    def copy_attachment_in_invoice(self):
        # Comment
        ir_attachment_obj = self.env['ir.attachment']
        for expense in self:
            if expense.invoice_id and expense.reference:
                if not isinstance(expense.id, int):
                    identi = self._origin.id
                else:
                    identi = expense.id

                attachment = ir_attachment_obj.search([
                    ('res_id','=', identi),
                    ('type','=', 'binary'),
                    ('res_model','=', self._name)
                ])
                if attachment:
                    values = {
                        'name': expense.reference +'.pdf',
                        'res_model': 'account.invoice',
                        'res_id': expense.invoice_id.id,
                        'type': 'binary',
                        'datas_fname': expense.reference +'.pdf',
                        'datas': attachment.datas
                    }
                    new_attachment = ir_attachment_obj.create(values)

    @api.onchange("invoice_id")
    def _onchange_invoice_id(self):
        """Get expense amount from invoice amount. Otherwise it will do a
           mismatch when trying to post the account move."""
        if self.invoice_id:
            self.quantity = 1
            self.unit_amount = self.invoice_id.amount_total
            #self.copy_attachment_in_invoice()

    
    @api.onchange("employee_id")
    def _onchange_employee_id(self):
        #comm
        if self.employee_id:
            if self.employee_id.def_acc_analytic_id and not self.analytic_account_id:
                self.analytic_account_id = self.employee_id.def_acc_analytic_id.id

class HrExpenseCode(models.Model):
    _name = "hr.expense.code"

    name = fields.Char(string='Código')
    product_id = fields.Many2one('product.product', string='Descripción')