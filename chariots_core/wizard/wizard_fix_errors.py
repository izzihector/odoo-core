# -*- coding: utf-8 -*-


from odoo import fields, models, api, _
from odoo.exceptions import UserError, ValidationError, Warning
from datetime import datetime, timedelta
import calendar
import logging


class WizardFixErrors(models.TransientModel):
    _name = 'chariots.wizard.fix.errors'
    _description = "Wizard Chariots Multicompañia"

    error_fix_selection = fields.Selection(
        string='Seleccionar tipo de arreglo',
        selection=[
            ('payment_inv_fix_acc_analytic_default', 'Arreglar pagos de fact. con cuenta analit. por defecto'),
            ('payment_inv_fix_very_acc_analytic', 'Arreglar pagos de fact. con varias cuentas analit.'),
            ('invoice_fix_acc_analytic_default', 'Arreglar facturas con cuenta analit. por defecto'),
            ('invoice_very_fix_acc_analytic_default', 'Arreglar facturas con varias cuentas analit.'),
            ('fix_account_move_journal', 'Regenerar asientos contables por Diario'),
            ('fix_create_payments', 'Generar pagos de las facturas'),
            ('fix_create_payments_by_store', 'Generar pagos de las facturas por tienda'),
            ('fix_create_no_sales', 'Generar Ventas KFC vacias'),
            ('fix_inv_payment_method', 'Arreglar asientos de pago de facturas kfc'),
            ('fix_attachments_cloud', 'Subir adjuntos facturas proveedor Drive'),
            ('fix_attachments_import_cloud', 'Forzar Importe facturas proveedor Drive'),
            ('fix_invoices_accounts', 'FIX: Cuentas Contables de Facturas'),
            ('fix_regenerate_acc_moves', 'Regenerar asientos contables de Facturas'),
            ('fix_inv_state', 'Cambiar estado facturas'),
            ('fix_invoices_account_analytic_default', 'Asociar cuentas analiticas a lineas de factura por Diario'),
            ('del_account_move_journal', 'Borrar asientos contables por Diario'),
            ('update_kfc_sale', 'Actualizar ventas y lineas de KFC'),
            ('update_import_residual_invoices', 'Actualizar importe residual por Diario'),
            ('delete_invoices', 'Eliminar facturas'),
            ('update_acc_analy_pay_kfc', 'Actualizar cuentas analiticas de pagos kfc'),
            ('new_kfc_sale_tax', 'Nuevos impuestos de ventas'),
            ('update_price_subtotal_signed', 'Actualizar subtotal de facturas por diario'),
            ('update_ca_journal', 'Actualizar CA de facturas por diario'),
            ('update_partner_st_line', 'Actualizar Empresas en extractos'),

        ],
        required=True
    )
    journal_id = fields.Many2one(string='Diario', comodel_name='account.journal')
    partner_id = fields.Many2one(string='Empresa', comodel_name='res.partner')

    acc_anal_id = fields.Many2one(string='Cuenta analitica', comodel_name='account.analytic.account')
    date_init = fields.Date(string='Fecha Inicio')
    date_from = fields.Date(string='Fecha Fin')

    def button_confirm(self):
        if self.error_fix_selection == 'fix_regenerate_acc_moves':
            self.fix_regenerate_acc_moves()
        if self.error_fix_selection == 'fix_inv_state':
            self.fix_inv_state()
        if self.error_fix_selection == 'fix_invoices_accounts':
            self.fix_invoices_accounts()
        if self.error_fix_selection == 'payment_inv_fix_acc_analytic_default':
            self.payment_inv_fix_acc_analytic_default()
        if self.error_fix_selection == 'payment_inv_fix_very_acc_analytic':
            self.payment_inv_fix_very_acc_analytic()
        if self.error_fix_selection == 'invoice_fix_acc_analytic_default':
            self.invoice_fix_acc_analytic_default()
        if self.error_fix_selection == 'invoice_very_fix_acc_analytic_default':
            self.invoice_very_fix_acc_analytic_default()
        if self.error_fix_selection == 'fix_account_move_journal':
            self.fix_account_move_journal()
        if self.error_fix_selection == 'fix_create_payments':
            self.fix_create_payments()
        if self.error_fix_selection == 'fix_inv_payment_method':
            self.fix_inv_payment_method()
        if self.error_fix_selection == 'fix_create_no_sales':
            self.fix_create_no_sales()
        if self.error_fix_selection == 'fix_attachments_cloud':
            self.fix_attachments_cloud()
        if self.error_fix_selection == 'fix_attachments_import_cloud':
            self.fix_attachments_import_cloud()
        if self.error_fix_selection == 'fix_invoices_account_analytic_default':
            self.fix_invoices_account_analytic_default()
        if self.error_fix_selection == 'del_account_move_journal':
            self.del_account_move_journal()
        if self.error_fix_selection == 'fix_create_payments_by_store':
            self.fix_create_payments_by_store()
        if self.error_fix_selection == 'update_kfc_sale':
            self.update_kfc_sale()
        if self.error_fix_selection == 'update_import_residual_invoices':
            self.update_import_residual_invoices()
        if self.error_fix_selection == 'delete_invoices':
            self.delete_invoices()
        if self.error_fix_selection == 'update_acc_analy_pay_kfc':
            self.update_acc_analy_pay_kfc()
        if self.error_fix_selection == 'new_kfc_sale_tax':
            self.new_kfc_sale_tax()
        if self.error_fix_selection == 'update_price_subtotal_signed':
            self.update_price_subtotal_signed()
        if self.error_fix_selection == 'update_ca_journal':
            self.update_ca_journal()
        if self.error_fix_selection == 'update_partner_st_line':
            self.update_partner_st_line()
    
    def update_partner_st_line(self):
        if not self.date_from or not self.date_init:
            raise UserError(_("Es necesario establecer las dos fechas"))
        
        bank_st_obj = self.env['account.bank.statement.line']
        bank_st = bank_st_obj.search([
            ('company_id', '=', self.env.user.company_id.id),
            ('date', '>=', self.date_init),
            ('date', '<=', self.date_from),
            ('account_payment_id', '!=', False),
        ])
        if bank_st:
            query_bnk_st_update = """
                UPDATE account_bank_statement_line as bnk_line SET
                partner_id = res.partner_id 
                FROM (SELECT pay.partner_id as partner_id, pay.id as payment_id
                    FROM account_payment as pay) res
                WHERE bnk_line.account_payment_id = res.payment_id and 
                bnk_line.date BETWEEN '{date_init}' and '{date_from}' and 
                bnk_line.partner_id is NULL and 
                bnk_line.account_payment_id is not NULL and 
                bnk_line.partner_id is NULL;
            """.format(
                date_init=self.date_init,
                date_from=self.date_from,
                company_id=self.env.user.company_id.id
            )
            self._cr.execute(query_bnk_st_update)
            self._cr.commit()
    
    def update_ca_journal(self):
        if not self.journal_id:
            raise UserError(_("Es necesario establecer un diario"))

        if not self.date_from or not self.date_init:
            raise UserError(_("Es necesario establecer las dos fechas"))
        
        invoice_obj = self.env['account.invoice']
        invoices = invoice_obj.search([
            ('company_id', '=', self.env.user.company_id.id),
            ('state', 'not in', ['cancel']),
            ('journal_id', '=', self.journal_id.id),
            ('date_invoice', '>=', self.date_init),
            ('date_invoice', '<=', self.date_from)
        ])
        if invoices:
            query_invoice_update = """
                UPDATE account_invoice_line as inv_line SET
                account_analytic_id = res.default_ac_analytic_id 
                FROM (SELECT inv.default_ac_analytic_id as default_ac_analytic_id, inv.id as inv_id
                    FROM account_invoice as inv
                    WHERE inv.default_ac_analytic_id is not NULL and inv.journal_id = {journal_id} and date_invoice BETWEEN '{date_init}' and '{date_from}' and company_id = {company_id}) res
                WHERE inv_line.invoice_id = res.inv_id and inv_line.account_analytic_id is NULL
            """.format(
                journal_id=self.journal_id.id,
                date_init=self.date_init,
                date_from=self.date_from,
                company_id=self.env.user.company_id.id
            )
            self._cr.execute(query_invoice_update)
            self._cr.commit()
    
    def update_price_subtotal_signed(self):
        if not self.journal_id:
            raise UserError(_("Es necesario establecer un diario"))

        if not self.date_from or not self.date_init:
            raise UserError(_("Es necesario establecer las dos fechas"))
        
        invoice_obj = self.env['account.invoice']
        invoices = invoice_obj.search([
            ('company_id', '=', self.env.user.company_id.id),
            ('state', 'not in', ['cancel']),
            ('journal_id', '=', self.journal_id.id),
            ('real_sale_date', '>=', self.date_init),
            ('real_sale_date', '<=', self.date_from)
        ])
        if invoices:
            query_invoice_update = """
                UPDATE account_invoice_line as inv_l SET
                price_subtotal_signed = inv_l.price_subtotal
                FROM (SELECT id 
                    FROM account_invoice
                    where real_sale_date BETWEEN '{date_init}' and '{date_from}' and journal_id = {journal_id} and company_id = {company_id} and state != 'cancel'
                    GROUP BY id) inv
                WHERE inv_l.invoice_id = inv.id 
            """.format(
                journal_id=self.journal_id.id,
                date_init=self.date_init,
                date_from=self.date_from,
                company_id=self.env.user.company_id.id
            )
            self._cr.execute(query_invoice_update)
            self._cr.commit()
    

    def new_kfc_sale_tax(self):
        self.env['chariots.import.kfc.sale'].query_kfc_sale_tax(date_init=self.date_init, date_end=self.date_from)
    
    def update_acc_analy_pay_kfc(self):
        self.env['account.move.line'].query_update_mv_lines_pay_kfc()
    
    def delete_invoices(self):
        account_invoice_kfc_one = self.env['ir.property'].sudo().search([('name', '=', 'account_invoice_kfc_one')])
        account_invoice_kfc_one = account_invoice_kfc_one.value_reference.split(',')
        account_invoice_kfc_one = int(account_invoice_kfc_one[1])
        account_invoice_kfc_one = self.env['account.invoice'].search([('id', '=', account_invoice_kfc_one)])
        #if account_invoice_kfc_one:
            #self._cr.execute("""
                #DELETE FROM account_invoice WHERE id = {inv_id};
            #""".format(inv_id=account_invoice_kfc_one.id))
            #self._cr.commit()
    

    def update_import_residual_invoices(self):
        if not self.journal_id:
            raise UserError(_("Es necesario establecer un diario"))

        if not self.date_from or not self.date_init:
            raise UserError(_("Es necesario establecer las dos fechas"))
        
        invoice_obj = self.env['account.invoice']
        invoices = invoice_obj.search([
            ('company_id', '=', self.env.user.company_id.id),
            ('state', 'not in', ['cancel']),
            ('journal_id', '=', self.journal_id.id),
            ('real_sale_date', '>=', self.date_init),
            ('real_sale_date', '<=', self.date_from)
        ])
        if invoices:
            for inv in invoices:
                if inv.residual == 0.00:
                    continue
                store_id = self.env['chariots.import.kfc.store'].search([('partner_id', '=', inv.partner_id.id)])
                if not store_id:
                    continue
                query = """
                    SELECT
                        s.payment_method_id payment_method_id,
                        kfc_paymethod.name payment_method_name,
                        SUM(s.amount_total_fix) amount_total_fix
                    FROM chariots_import_kfc_sale_tax s 
                    LEFT JOIN chariots_import_kfc_paymethod kfc_paymethod ON s.payment_method_id = kfc_paymethod.id
                    WHERE s.date >= '{year}-{month}-{day}' AND s.date <= '{year}-{month}-{day}' AND s.store_id = {store}
                    GROUP BY s.payment_method_id, kfc_paymethod.name;
                """.format(
                    year=str(inv.real_sale_date.year),
                    month=str(inv.real_sale_date.month).zfill(2),
                    day=str(inv.real_sale_date.day).zfill(2),
                    store=store_id.id
                )
                self._cr.execute(query)
                results = self._cr.fetchall()
                if not results:
                    continue
                
                amount_total_pay = 0
                #Recorremos las líneas de pago de KFC
                for payment_method_id, payment_method_name, amount_total_fix in results:
                    if not payment_method_id:
                        logging.info("No existen método de pago para la factura {}".format(inv.id))
                        continue
                    amount_total_pay += amount_total_fix
                amount_total_pay = round(amount_total_pay, 2)
                if inv.residual != 0:
                    residual = round(round(inv.residual, 2) - amount_total_pay, 2)
                    abs_residual = abs(residual)
                    if abs_residual == 0.00 or residual < 0:
                        residual = 0.00
                    query_invoice_update = """
                        UPDATE account_invoice
                        SET residual = {residual}, residual_signed = {residual_signed}, residual_company_signed = {residual_company_signed}
                        WHERE id = {inv_id};
                    """.format(
                        inv_id=inv.id,
                        residual=residual,
                        residual_signed=residual,
                        residual_company_signed=residual,
                    )
                    self._cr.execute(query_invoice_update)
                    self._cr.commit()

            query_invoice_update = """
                UPDATE account_invoice
                SET state = 'paid', reconciled = TRUE
                WHERE residual = 0 and journal_id = {journal_id};
            """.format(
                journal_id=self.journal_id.id,
            )
            self._cr.execute(query_invoice_update)
            self._cr.commit()
                    

    def update_kfc_sale(self):
        self.env['chariots.import.kfc.sale'].query_update_kfc_sales()

    def del_account_move_journal(self):
        if not self.journal_id:
            raise UserError(_("Es necesario establecer un diario"))
        if not self.date_from or not self.date_init:
            raise UserError(_("Es necesario establecer las dos fechas"))

        self._cr.execute("""
            DELETE FROM account_move_line WHERE journal_id = {journal_id} AND create_date BETWEEN '{date_init}' AND '{date_from}';
            DELETE FROM account_move WHERE journal_id = {journal_id} AND create_date BETWEEN '{date_init}' AND '{date_from}';
        """.format(journal_id=self.journal_id.id, date_init=self.date_init, date_from=self.date_from))
        self._cr.commit()
    
    def fix_invoices_account_analytic_default(self):
        if not self.journal_id:
            raise UserError(_("Es necesario establecer un diario"))

        if not self.date_from or not self.date_init:
            raise UserError(_("Es necesario establecer las dos fechas"))

        invoice_obj = self.env['account.invoice']
        invoices = invoice_obj.search([
            ('company_id', '=', self.env.user.company_id.id),
            ('state', 'not in', ['cancel']),
            ('default_ac_analytic_id', '!=', False),
            ('journal_id', '=', self.journal_id.id),
            ('date_invoice', '>=', self.date_init),
            ('date_invoice', '<=', self.date_from)
        ])
        if invoices:
            for inv in invoices:
                if inv.default_ac_analytic_id:
                    query_invoice_update = """
                        UPDATE account_invoice_line
                        SET account_analytic_id = {account_analytic_id} 
                        WHERE invoice_id = {inv_id};
                    """.format(
                        inv_id=inv.id,
                        account_analytic_id=inv.default_ac_analytic_id.id
                    )
                    self._cr.execute(query_invoice_update)
                    self._cr.commit()

    def fix_attachments_import_cloud(self):
        if not self.date_from or not self.date_init:
            raise UserError(_("Es necesario establecer las dos fechas"))
        self.env['ir.attachment'].cron_sync_remote_invoice(date_from=self.date_init, date_to=self.date_from)

    def fix_attachments_cloud(self):
        domain = [('type', 'in', ['in_invoice', 'in_refund']), ('state', 'not in', ['draft', 'cancel'])]
        if self.date_from and self.date_init:
            domain.append(('date_invoice', '>=', self.date_init))
            domain.append(('date_invoice', '<=', self.date_from))
        invoice_obj = self.env['account.invoice']
        invoices = invoice_obj.search(domain)
        if invoices:
            for inv in invoices:
                inv.upload_file_inv_drive()

    def fix_inv_payment_method(self):
        if not self.journal_id:
            raise UserError(_("Es necesario establecer un diario"))
        if not self.date_from or not self.date_init:
            raise UserError(_("Es necesario establecer las dos fechas"))

        invoices = self.env['account.invoice'].search(
            [('journal_id', '=', self.journal_id.id), ('state', 'in', ['open', 'paid']),
             ('real_sale_date', '>=', self.date_init), ('real_sale_date', '<=', self.date_from)])
        if invoices:
            for invoice in invoices:
                invoice.generate_payment_by_method()
    
    def fix_regenerate_acc_moves(self):
        if not self.journal_id:
            raise UserError(_("Es necesario establecer un diario"))
        if not self.date_from or not self.date_init:
            raise UserError(_("Es necesario establecer las dos fechas"))

        invoices = self.env['account.invoice'].search(
            [('journal_id', '=', self.journal_id.id), ('state', 'in', ['open', 'paid']),
             ('date_invoice', '>=', self.date_init), ('date_invoice', '<=', self.date_from)])
        if invoices:
            for invoice in invoices:
                if invoice.move_id:
                    invoice.move_id = [(2, invoice.move_id.id, False)]
                
                invoice.with_context(check_move_validity=False).action_move_create()
                invoice.move_id.create_lines_cnj()
    
    def fix_inv_state(self):
        if not self.journal_id:
            raise UserError(_("Es necesario establecer un diario"))
        if not self.date_from or not self.date_init:
            raise UserError(_("Es necesario establecer las dos fechas"))
        
        self.env.cr.execute("""
            UPDATE account_invoice	
            SET state = 'paid'	
            WHERE journal_id = {} and date_invoice BETWEEN '{}' and '{}' and move_id is not null and move_payment_id is not null and state = 'open'
            """.format(self.journal_id.id, self.date_init, self.date_from))
        self.env.cr.commit()


    def fix_create_no_sales(self):
        date_from = self.date_init
        date_to = self.date_from
        kfc_sale_obj = self.env['chariots.import.kfc.sale']
        kfc_store_obj = self.env['chariots.import.kfc.store']
        all_stores = kfc_store_obj.search([])
        month_start = date_from.month
        month_end = date_to.month
        for num_month in range(month_start, month_end + 1):
            if num_month == month_start and num_month == month_end:
                day_month_start = date_from.day
                day_month_end = date_to.day
            elif num_month == month_start:
                day_month_start = date_from.day
                day_month_end = calendar.monthrange(date_from.year, month_start)[1]
            elif num_month == month_end:
                day_month_start = 1
                day_month_end = date_to.day
            else:
                day_month_start = 1
                day_month_end = calendar.monthrange(date_to.year, num_month)[1]

            for day in range(day_month_start, day_month_end + 1):
                no_sales = []
                for store in all_stores:
                    query_kfc = """
                        SELECT
                            store.id as store_id,
                            store.name as name,
                            COUNT(sale.id) as num_sales,
                            SUM(sale.amount_total) as amount_total_total,
                            AVG(sale.amount_total) as sale_medium,
                            is_imported
                        FROM chariots_import_kfc_store as store
                        LEFT JOIN chariots_import_kfc_sale as sale ON sale.store = store.external_id 
                        WHERE sale.date = '{}-{}-{}' and sale.store = {}
                        GROUP BY store.id, sale.date, is_imported
                        ORDER BY name ASC, sale.date 
                    """.format(str(date_to.year), str(num_month).zfill(2), str(day).zfill(2), store.external_id)
                    kfc_sale_obj._cr.execute(query_kfc)
                    results_kfc_sale = kfc_sale_obj._cr.fetchall()
                    if not results_kfc_sale:
                        date_actual = datetime(date_to.year, num_month, day)
                        no_sales.append({'store': store, 'date': date_actual})

                if no_sales:
                    kfc_sale_obj.new_sales(no_sales)

    def fix_create_payments(self):
        if not self.journal_id:
            raise UserError(_("Es necesario establecer un diario"))

        domain = [('journal_id', '=', self.journal_id.id), ('state', '=', 'open')]
        if self.date_from and self.date_init:
            domain.append(('date_invoice', '>=', self.date_init))
            domain.append(('date_invoice', '<=', self.date_from))
        invoice_obj = self.env['account.invoice']
        invoices = invoice_obj.search(domain)
        if invoices:
            for inv in invoices:
                inv.generate_payment_by_method()

    def fix_create_payments_by_store(self):
        if not self.partner_id:
            raise UserError(_("Es necesario establecer una empresa"))
        
        if not self.date_from and not self.date_init:
            raise UserError(_("Es necesario establecer fechas"))

        domain = [('journal_id', '=', self.journal_id.id), ('state', 'not in', ['draft','cancel']), ('partner_id', '=', self.partner_id.id)]
        if self.date_from and self.date_init:
            domain.append(('real_sale_date', '>=', self.date_init))
            domain.append(('real_sale_date', '<=', self.date_from))
        invoice_obj = self.env['account.invoice']
        invoices = invoice_obj.search(domain)
        if invoices:
            for inv in invoices:
                inv.generate_payment_by_method()

    def fix_account_move_journal(self):
        if not self.journal_id:
            raise UserError(_("Es necesario establecer un diario"))
        if not self.date_from or not self.date_init:
            raise UserError(_("Es necesario establecer las dos fechas"))
        domain = [
            ('journal_id', '=', self.journal_id.id),
            ('state', 'in', ['open', 'paid']),
            ('date_invoice', '>=', self.date_init),
            ('date_invoice', '<=', self.date_from)
        ]
        if self.acc_anal_id:
            domain.append(('default_ac_analytic_id', '=', self.acc_anal_id.id))

        invoices = self.env['account.invoice'].search(domain)
        if invoices:
            for invoice in invoices:
                if invoice.move_id:
                    if invoice.tax_line_ids:
                        tax_id = self.env['ir.property'].sudo().search([('name', '=', 'account_tax_one')])
                        tax_id = tax_id.value_integer
                        tax_id = self.env['account.tax'].search([('id', '=', tax_id)])
                        if tax_id:
                            tax_line = invoice.tax_line_ids.filtered(lambda l: l.tax_id.id == tax_id.id)
                            if tax_line:
                                if invoice.type == 'out_invoice':
                                    tax_line.write({'account_id': tax_id.account_id.id})
                                else:
                                    if invoice.type == 'out_refund':
                                        tax_line.write({'account_id': tax_id.refund_account_id.id})

                    move_id = invoice.move_id
                    if invoice.move_id.state == 'posted':
                        move_id.write({'state': 'draft'})
                        invoice.move_id = [(3, move_id.id)]
                        move_id.unlink()
                        invoice.action_move_create()
                        if invoice.journal_id.code == 'CANJE':
                            invoice.move_id.create_lines_cnj()
                    else:
                        invoice.move_id = [(3, move_id.id)]
                        move_id.unlink()
                        invoice.action_move_create()
                        if invoice.journal_id.code == 'CANJE':
                            invoice.move_id.create_lines_cnj()
                else:
                    invoice.action_move_create()
                    if invoice.journal_id.code == 'CANJE':
                        invoice.move_id.create_lines_cnj()

    def payment_inv_fix_acc_analytic_default(self):
        payment_obj = self.env['account.payment']
        payments = payment_obj.search([('company_id', '=', self.env.user.company_id.id)])
        payments = payments.filtered(lambda pay: pay.invoice_ids)
        if payments:
            for pay in payments:
                invoice_ids = pay.invoice_ids.filtered(lambda inv: inv.default_ac_analytic_id)
                reconcile_invoice_ids = pay.reconciled_invoice_ids.filtered(lambda inv: inv.default_ac_analytic_id)
                default_account_analytic = ''
                if not invoice_ids and reconcile_invoice_ids:
                    continue

                if invoice_ids:
                    default_account_analytic = invoice_ids[0].default_ac_analytic_id
                else:
                    if not invoice_ids and reconcile_invoice_ids:
                        default_account_analytic = reconcile_invoice_ids[0].default_ac_analytic_id

                if default_account_analytic and pay.move_line_ids:
                    for line in pay.move_line_ids:
                        if line.analytic_account_id and line.analytic_account_id.id == default_account_analytic.id:
                            continue
                        if line.move_id.default_account_analytic and line.move_id.default_account_analytic.id == default_account_analytic.id:
                            continue
                        move_id = line.move_id
                        move_id.write({'default_account_analytic': default_account_analytic.id})

    def payment_inv_fix_very_acc_analytic(self):
        payment_obj = self.env['account.payment']
        payments = payment_obj.search([('company_id', '=', self.env.user.company_id.id)])
        payments = payments.filtered(lambda pay: pay.invoice_ids)
        if payments:
            for pay in payments:
                invoice_ids = pay.invoice_ids.filtered(lambda inv: not inv.default_ac_analytic_id)
                reconcile_invoice_ids = pay.reconciled_invoice_ids.filtered(lambda inv: inv.default_ac_analytic_id)
                if not invoice_ids and reconcile_invoice_ids:
                    continue

                if not invoice_ids and reconcile_invoice_ids:
                    invoice_ids = reconcile_invoice_ids

                if pay.move_line_ids and invoice_ids:
                    for line in pay.move_line_ids:
                        lines_account = []

                        if line.analytic_line_ids:
                            continue

                        move_id = line.move_id
                        for invoice in invoice_ids:
                            for inv_line in invoice.invoice_line_ids.filtered(lambda l: l.account_analytic_id):
                                line_analytics = ''
                                if line.analytic_line_ids:
                                    line_analytics = line.analytic_line_ids.filtered(
                                        lambda l: l.account_id.id == inv_line.account_analytic_id.id)
                                if line_analytics:
                                    continue
                                cant = inv_line.quantity
                                imp = 0
                                if line.debit > 0:
                                    imp = inv_line.price_total * -1
                                else:
                                    imp = inv_line.price_total

                                dict_create = {
                                    'name': line.name,
                                    'ref': move_id.ref if move_id else '',
                                    'partner_id': line.partner_id.id if line.partner_id else False,
                                    'date': move_id.date,
                                    'company_id': move_id.company_id.id,
                                    'general_account_id': line.account_id.id,
                                    'unit_amount': cant,
                                    'amount': imp,
                                    'account_id': inv_line.account_analytic_id.id,
                                    'product_id': inv_line.product_id.id,
                                    'product_uom_id': inv_line.uom_id.id
                                }
                                lines_account.append((0, 0, dict_create))

                        if lines_account:
                            line.write({'analytic_line_ids': lines_account})

    def invoice_fix_acc_analytic_default(self):
        invoice_obj = self.env['account.invoice']
        invoices = invoice_obj.search([
            ('company_id', '=', self.env.user.company_id.id),
            ('state', 'not in', ['cancel', 'draft']),
            ('move_id', '!=', False),
            ('default_ac_analytic_id', '!=', False),

        ])
        if invoices:
            for inv in invoices:
                if inv.move_id.default_account_analytic:
                    if inv.move_id.default_account_analytic.id == inv.default_ac_analytic_id.id:
                        continue
                move_id = inv.move_id
                move_id.write({'default_account_analytic': inv.default_ac_analytic_id.id})

    def invoice_very_fix_acc_analytic_default(self):
        invoice_obj = self.env['account.invoice']
        invoices = invoice_obj.search([
            ('company_id', '=', self.env.user.company_id.id),
            ('state', 'not in', ['cancel', 'draft']),
            ('move_id', '!=', False),
            ('default_ac_analytic_id', '=', False),

        ])
        if invoices:
            for invoice in invoices:
                if not invoice.move_id:
                    continue
                move_id = invoice.move_id
                if not move_id.line_ids:
                    continue
                line_ids = move_id.line_ids.filtered(lambda line: not line.analytic_account_id)
                move_id.create_new_analytic_lines(invoice, line_ids)

    def fix_invoices_accounts(self):
        old_acc_id = 193
        journal_id = self.journal_id.id
        inv_obj = self.env['account.invoice'].sudo().with_context(company_id=1, force_company=1)
        affected_invoices = inv_obj.search([
            ('journal_id.id', '=', journal_id),
            ('account_id.id', '=', old_acc_id),
        ])
        for invoice in affected_invoices:
            acc_id = invoice.partner_id.property_account_receivable_id
            sql = """
                UPDATE account_move_line
                SET account_id = {acc_id}
                WHERE account_id = {old_acc_id} AND invoice_id = {inv_id} AND move_id = {move_id};
                UPDATE account_invoice
                SET account_id = {acc_id}
                WHERE account_id = {old_acc_id} AND id = {inv_id};
            """.format(
                acc_id=acc_id.id,
                old_acc_id=old_acc_id,
                inv_id=invoice.id,
                move_id=invoice.move_id.id
            )
            self._cr.execute(sql)
