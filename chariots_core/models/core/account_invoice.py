# -*- coding: utf-8 -*-

from odoo import api, fields, exceptions, models, _
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT
from odoo.exceptions import UserError, ValidationError, Warning
from odoo.modules.registry import Registry

from datetime import datetime
import logging
import json

# mapping invoice type to refund type
TYPE2REFUND = {
    'out_invoice': 'out_refund',        # Customer Invoice
    'in_invoice': 'in_refund',          # Vendor Bill
    'out_refund': 'out_invoice',        # Customer Credit Note
    'in_refund': 'in_invoice',          # Vendor Credit Note
}

class AccountInvoice(models.Model):
    _inherit = 'account.invoice'
    _order = "real_sale_date DESC, date_invoice DESC, default_ac_analytic_id ASC, state ASC"

    reference = fields.Char(required=False, domain=[('type', 'in', ['in_refund', 'in_invoice'])])
    default_ac_analytic_id = fields.Many2one('account.analytic.account', string='Cuenta Analítica')
    is_flagged = fields.Boolean(string="Marcada", default=False)
    is_assess = fields.Boolean(string='Lista para contabilizar', default=False)
    move_payment_id = fields.Many2one(string='Asiento de pago KFC', comodel_name='account.move')
    account_move_state = fields.Selection(string='Estado Asiento', related='move_id.state')
    account_journal_name = fields.Char(string='Nombre Diario', related='journal_id.name')
    account_journal_code = fields.Char(string='Código Diario', related='journal_id.code')

    READONLY_STATES = {
        'draft': [('readonly', False)],
        'open': [('readonly', False)],
    }
    PUBLISH_STATES = ['open', 'paid']
    invoice_line_ids = fields.One2many(states=READONLY_STATES)
    tax_line_ids = fields.One2many(states=READONLY_STATES)
    real_sale_date = fields.Date(string="Fecha de Venta Real")
    is_grouped_invoice = fields.Boolean(string="Es factura agrupada", default=False)
    is_substitute_invoice = fields.Boolean(string="Es factura sustitutiva", default=False)
    substituted_invoice_ids = fields.Many2many(
        comodel_name="account.invoice",
        relation="account_invoice_substituted_rel",
        column1="substitute_invoice_id", column2="original_invoice_id",
        string="Facturas sustituidas"
    )
    substitute_from_invoice_ids = fields.Many2many(
        comodel_name="account.invoice",
        relation="account_invoice_substituted_rel",
        column2="substitute_invoice_id", column1="original_invoice_id",
        string="Facturas de canje"
    )
    serial_tickets_code_sii = fields.Char(string="Secuencia de Ticket para SII")
    invoice_migrated = fields.Boolean(
        string="Factura Migrada",
        default=False
    )
    move_migrated = fields.Boolean(
        string="Asiento Migrado",
        default=False
    )
    # Esto es solo para pasarla la informacion de uno a otro
    payment_origin = fields.Char(string="Vía de Pag.", related='partner_id.payment_origin', readonly=True, store=True)
    payment_origin_sel = fields.Selection(
        string="Vía de Pago",
        related='partner_id.payment_origin_sel',
        readonly=True,
        store=True
    )
    # Líneas de KFC
    kfc_line_ids = fields.One2many(
        string="Líneas de Venta KFC",
        comodel_name="chariots.import.kfc.sale.line",
        inverse_name="invoice_id"
    )
    kfc_line_count = fields.Integer(
        string="Nº líneas",
        compute="_compute_kfc_line",
    )

    # Lotes de pago com
    batch_payment_ids = fields.Many2many(
        string="Lotes de pago",
        compute="_compute_batch_payment",

    )
    batch_payment_count = fields.Integer(
        string="Nº Lotes de pago",
        compute="_compute_batch_payment",

    )    
    expense_ids = fields.One2many('hr.expense', 'invoice_id', string='Gastos')
    
    @api.one
    @api.depends('invoice_line_ids.price_subtotal', 'tax_line_ids.amount', 'tax_line_ids.amount_rounding',
                 'currency_id', 'company_id', 'date_invoice', 'type')
    def _compute_amount(self):
        if self.journal_id.code != 'INV':
            return super(AccountInvoice, self)._compute_amount()
    

    @api.one
    @api.depends(
        'state', 'currency_id', 'invoice_line_ids.price_subtotal',
        'move_id.line_ids.amount_residual',
        'move_id.line_ids.currency_id')
    def _compute_residual(self):
        if self.journal_id.code != 'INV':
            return super(AccountInvoice, self)._compute_residual()

    @api.multi
    @api.depends('payment_ids')
    def _compute_batch_payment(self):
        for inv in self:
            count = 0
            batch_payment_ids = []
            if inv.payment_ids:
                payment_ids = inv.payment_ids.filtered(lambda x: x.state not in ['draft', 'cancelled'])
                for pay in payment_ids:
                    if pay.batch_payment_id:
                        if pay.batch_payment_id.id not in batch_payment_ids:
                            batch_payment_ids.append(pay.batch_payment_id.id)
                count = len(batch_payment_ids)
            inv.batch_payment_ids = batch_payment_ids
            inv.batch_payment_count = count

    @api.multi
    def action_view_batch_payment(self):
        self.ensure_one()
        action = {
            'name': _('Lotes de pago'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.batch.payment',
            'target': 'current',
        }
        batch_payment_ids = self.batch_payment_ids.ids
        if len(batch_payment_ids) == 1:
            action['res_id'] = batch_payment_ids[0]
            action['view_mode'] = 'form'
        else:
            action['view_mode'] = 'tree,form'
            action['domain'] = [('id', 'in', batch_payment_ids)]
        return action

    @api.multi
    @api.depends('kfc_line_ids')
    def _compute_kfc_line(self):
        for inv in self:
            inv.kfc_line_count = len(inv.kfc_line_ids.ids)

    @api.multi
    def action_go_kfc_sale_line(self):
        self.ensure_one()
        action = self.env.ref('chariots_core.actions_kfc_sale_line').read()[0]
        action['domain'] = [('invoice_id', '=', self.id)]
        return action

    @api.multi
    def _send_invoice_to_sii(self):
        try:
            for invoice in self:
                if invoice.date_invoice and invoice.type in ['out_invoice', 'out_refund']:
                    if invoice.date != invoice.date_invoice:
                        invoice.date = invoice.date_invoice
            super(AccountInvoice, invoice)._send_invoice_to_sii()
        except:
            self.env.cr.commit()
            raise

    @api.model
    def _get_sii_tax_dict(self, tax_line, sign):
        """Get the SII tax dictionary for the passed tax line.

        :param self: Single invoice record.
        :param tax_line: Tax line that is being analyzed.
        :param sign: Sign of the operation (only refund by differences is
          negative).
        :return: A dictionary with the corresponding SII tax values.
        """
        tax = tax_line.tax_id
        if tax.amount_type == 'group':
            tax_type = abs(tax.children_tax_ids.filtered('amount')[:1].amount)
        elif tax.sii_force_amount:
            tax_type = abs(tax.sii_force_amount)
        else:
            tax_type = abs(tax.amount)
        base = tax_line.force_base_company if tax_line.base_company != tax_line.force_base_company else tax_line.base_company
        # base = tax_line.base_company original
        tax_dict = {
            'TipoImpositivo': str(tax_type),
            'BaseImponible': sign * abs(base),
        }
        if self.type in ['out_invoice', 'out_refund']:
            key = 'CuotaRepercutida'
        else:
            key = 'CuotaSoportada'
        if not tax.sii_force_amount:
            tax_dict[key] = sign * abs(tax_line.amount_company)
        else:
            tax_dict[key] = sign * abs(round(base * tax.sii_force_amount / 100, 2))
        # Recargo de equivalencia
        re_tax_line = self._get_sii_tax_line_req(tax)
        if re_tax_line:
            tax_dict['TipoRecargoEquivalencia'] = (
                abs(re_tax_line.tax_id.amount)
            )
            tax_dict['CuotaRecargoEquivalencia'] = (
                    sign * abs(re_tax_line.amount_company)
            )
        return tax_dict

    # Método para calcular automáticamente la descripcion del SII
    @api.depends('invoice_line_ids', 'invoice_line_ids.name', 'company_id', 'sii_manual_description')
    def _compute_sii_description(self):
        for invoice in self:
            description = ''
            if invoice.state not in ['draft', 'validate']:
                if invoice.partner_id:
                    if invoice.partner_id.sii_description_method == 'custom':
                        if invoice.partner_id.custom_description_sii:
                            description = invoice.partner_id.custom_description_sii
                        else:
                            description = '/'
                    elif invoice.partner_id.sii_description_method == 'first_line':
                        if invoice.invoice_line_ids:
                            invoice_first_line = invoice.invoice_line_ids[0]
                            if invoice_first_line and invoice_first_line.name:
                                description = invoice_first_line.name
            if not description:
                description = '/'

            invoice.sii_description = description

    @api.multi
    def send_sii(self):
        invoices = self.filtered(
            lambda i: (
                    i.sii_enabled and i.state in ['open', 'in_payment', 'paid'] and
                    i.sii_state not in ['sent', 'cancelled']
            )
        )
        if not invoices._cancel_invoice_jobs():
            raise exceptions.Warning(_(
                'You can not communicate this invoice at this moment '
                'because there is a job running!'))
        invoices._process_invoice_for_sii_send()

    @api.multi
    def _send_invoice_to_sii(self):
        for invoice in self.filtered(lambda i: i.state in ['open', 'in_payment', 'paid']):
            serv = invoice._connect_sii(invoice.type)
            if invoice.sii_state == 'not_sent':
                tipo_comunicacion = 'A0'
            else:
                tipo_comunicacion = 'A1'
            header = invoice._get_sii_header(tipo_comunicacion)
            inv_vals = {
                'sii_header_sent': json.dumps(header, indent=4),
            }
            try:
                inv_dict = invoice._get_sii_invoice_dict()
                inv_vals['sii_content_sent'] = json.dumps(inv_dict, indent=4)
                if invoice.type in ['out_invoice', 'out_refund']:
                    res = serv.SuministroLRFacturasEmitidas(
                        header, inv_dict)
                elif invoice.type in ['in_invoice', 'in_refund']:
                    res = serv.SuministroLRFacturasRecibidas(
                        header, inv_dict)
                # TODO Facturas intracomunitarias 66 RIVA
                # elif invoice.fiscal_position_id.id == self.env.ref(
                #     'account.fp_intra').id:
                #     res = serv.SuministroLRDetOperacionIntracomunitaria(
                #         header, invoices)
                res_line = res['RespuestaLinea'][0]
                if res['EstadoEnvio'] == 'Correcto':
                    inv_vals.update({
                        'sii_state': 'sent',
                        'sii_csv': res['CSV'],
                        'sii_send_failed': False,
                    })
                elif res['EstadoEnvio'] == 'ParcialmenteCorrecto' and \
                        res_line['EstadoRegistro'] == 'AceptadoConErrores':
                    inv_vals.update({
                        'sii_state': 'sent_w_errors',
                        'sii_csv': res['CSV'],
                        'sii_send_failed': True,
                    })
                else:
                    inv_vals['sii_send_failed'] = True
                if ('sii_state' in inv_vals and
                        not invoice.sii_account_registration_date and
                        invoice.type[:2] == 'in'):
                    inv_vals['sii_account_registration_date'] = (
                        self._get_account_registration_date()
                    )
                inv_vals['sii_return'] = res
                send_error = False
                if res_line['CodigoErrorRegistro']:
                    send_error = "{} | {}".format(
                        str(res_line['CodigoErrorRegistro']),
                        str(res_line['DescripcionErrorRegistro'])[:60])
                inv_vals['sii_send_error'] = send_error
                invoice.write(inv_vals)
            except Exception as fault:
                new_cr = Registry(self.env.cr.dbname).cursor()
                env = api.Environment(new_cr, self.env.uid, self.env.context)
                invoice = env['account.invoice'].browse(invoice.id)
                inv_vals.update({
                    'sii_send_failed': True,
                    'sii_send_error': repr(fault)[:60],
                    'sii_return': repr(fault),
                })
                invoice.write(inv_vals)
                new_cr.commit()
                new_cr.close()
                raise

    @api.multi
    def invoice_validate(self):
        account_journal_kfc = self.env['account.journal'].search([('code', '=', 'INV')], limit=1)
        for invoice in self:
            if not invoice.invoice_line_ids:
                continue
            invoice_lines = invoice.invoice_line_ids.filtered(
                lambda line: not line.invoice_line_tax_ids and line.display_type not in ['line_note', 'line_section'])
            if invoice_lines:
                raise UserError("Todas las lineas de las facturas tienen que tener mínimo un impuesto")

        self._compute_sii_description()
        for invoice in self:
            # Pasamos la factura de borrador a abierto
            if invoice.state == 'draft':
                if invoice.partner_id not in invoice.message_partner_ids:
                    if not invoice.reference and invoice.type == 'out_invoice':
                        invoice.reference = invoice._get_computed_reference()
                    if invoice.move_id:
                        invoice.move_id.ref = invoice.reference
                invoice._check_duplicate_supplier_reference()
                self.env.cr.execute("""
                            UPDATE account_invoice	
                            SET state = 'open'	
                            WHERE id = {}
                            """.format(invoice.id))
                self.env.cr.commit()
                if invoice.date_invoice and invoice.type in ['out_invoice', 'out_refund']:
                    if invoice.date != invoice.date_invoice:
                        invoice.date = invoice.date_invoice
                if invoice.journal_id.id == account_journal_kfc.id:
                    invoice.generate_payment_by_method()
                if invoice.type in ['in_invoice', 'in_refund']:
                    invoice.upload_file_inv_drive()

            if invoice.move_id:
                invoice._remove_move_if_must_and_exists()

        return True

    @api.multi
    def action_invoice_open(self):
        for invoice in self:
            if not invoice.invoice_line_ids:
                if invoice.real_sale_date:
                    date = datetime.strptime(str(invoice.real_sale_date), DEFAULT_SERVER_DATE_FORMAT).strftime(
                        '%d/%m/%Y')
                    raise UserError(
                        "La factura del cliente {} con fecha de venta real {} no tiene lineas de factura".format(
                            invoice.partner_id.display_name, date))
                else:
                    date = datetime.strptime(str(invoice.invoice_date), DEFAULT_SERVER_DATE_FORMAT).strftime('%d/%m/%Y')
                    raise UserError("La factura del cliente {} con fecha factura {} no tiene lineas de factura".format(
                        invoice.partner_id.display_name, date))
        return super(AccountInvoice, self).action_invoice_open()

   
    @api.multi
    def _get_sii_invoice_dict_out(self, cancel=False):
        inv_dict = super(AccountInvoice, self)._get_sii_invoice_dict_out(cancel=cancel)
        if self.is_grouped_invoice:
            inv_dict['FacturaExpedida']['TipoFactura'] = 'F4'
            if self.serial_tickets_code_sii:
                codes = self.serial_tickets_code_sii.split(':')
                # inv_dict['FacturaExpedida']['NumSerieFacturaEmisor'] = codes[0]
                inv_dict['IDFactura']['NumSerieFacturaEmisorResumenFin'] = codes[1]
        elif self.journal_id.code == 'CANJE' or self.is_substitute_invoice:
            self.is_substitute_invoice = True
            inv_dict['FacturaExpedida']['TipoFactura'] = 'F3'
        return inv_dict

    @api.multi
    def _get_sii_invoice_dict_in(self, cancel=False):
        inv_dict = super(AccountInvoice, self)._get_sii_invoice_dict_in(cancel=cancel)
        if 'FacturaRecibida' in inv_dict:
            date_array = str(self.date).split('-')
            inv_dict['FacturaRecibida']['FechaOperacion'] = "{}-{}-{}".format(date_array[2], date_array[1],
                                                                              date_array[0])
        return inv_dict

    @api.multi
    def action_asses_validated(self):
        """
        Método se encarga de contabilizar la factura que ya ha sido validada. Es obligatorio que esté en algún estado
        que sea permitido en la constante PUBLISH_STATES
        :return: Void
        """
        # journal_cnj = self.env['account.journal'].search([('code', '=', 'CANJE')], limit=1)
        for invoice in self:
            if invoice.state not in self.PUBLISH_STATES:
                raise ValidationError("La factura debe estar validada para poder ser contabilizada")
            if not invoice.move_id:
                raise ValidationError("La factura {} no tiene asiento contable".format(invoice.number))
            if invoice.move_id.state == 'posted':
                continue
            invoice.is_assess = True
            invoice.move_id.post(invoice=invoice)
            # if invoice.journal_id.id == journal_cnj:
            #    invoice.generate_refund_invoice()

    @api.one
    def generate_refund_invoice(self):
        """
        Método se encarga de generar una factura rectificativa al diario de KFC solo si el diario de la factura es Canje
        :return: Void"""
        # Comprobamos que el id exista en los diarios
        account_journal_kfc = self.env['account.journal'].search([('code', '=', 'INV')], limit=1)
        if account_journal_kfc:
            # Si existe el diario de Kfc creamos la factura
            if self.default_ac_analytic_id and self.invoice_line_ids and self.type == 'out_invoice':
                kfc_partner = self.env['chariots.import.kfc.store'].search(
                    [('analytic_account_id', '=', self.default_ac_analytic_id.id)])
                if kfc_partner:
                    dicc_invoice = {
                        'partner_id': kfc_partner.partner_id.id,
                        'default_ac_analytic_id': self.default_ac_analytic_id.id,
                        'journal_id': account_journal_kfc.id,
                        'date_invoice': self.date_invoice,
                        'type': 'out_refund'
                    }
                    invoice_refund = self.env[self._name].create(dicc_invoice)
                    if invoice_refund:
                        for line in self.invoice_line_ids:
                            dicc_invoice_line = {
                                'account_analytic_id': invoice_refund.default_ac_analytic_id.id,
                                'product_id': line.product_id.id,
                                'name': line.name,
                                'account_id': line.account_id.id,
                                'quantity': line.quantity,
                                'price_unit': line.price_unit,
                                'price_subtotal': line.price_subtotal,
                                'invoice_id': invoice_refund.id
                            }
                            account_line_refund = self.env['account.invoice.line'].create(dicc_invoice_line)
                            if account_line_refund:
                                if line.analytic_tag_ids:
                                    account_line_refund.write({'analytic_tag_ids': [(6, 0, line.analytic_tag_ids.ids)]})
                                if line.invoice_line_tax_ids:
                                    account_line_refund.write(
                                        {'invoice_line_tax_ids': [(6, 0, line.invoice_line_tax_ids.ids)]})

                    invoice_refund._onchange_invoice_line_ids()
                    invoice_refund._compute_amount()
                    invoice_refund._compute_residual()
                    self.refund_invoice_ids = [(4, invoice_refund.id)]

    @api.one
    def action_invoice_canceled(self):
        """
        Método se encarga de borrar el asiento contable en estado borrador de una factura y pasar la factura ha estado cancelado solo cuando esta
        en estado abierto 
        :return: Void
        """
        if not self.state == 'open':
            raise ValidationError("La factura debe estar en estado abierta para poder cancelarla")
        if self.state == 'open' and self.account_move_state != 'draft':
            raise ValidationError(
                "La factura debe estar en estado abierto y el asiento contable estar en borrador para poder cancelarla")
        move_id = self.move_id
        move_del = self.env['account.move'].search([('id', '=', move_id.id)])
        self.move_id = [(5, 0, 0)]
        move_del.unlink()
        dicc_write = {
            'state': 'cancel'
        }

        self.write(dicc_write)
        if self.sii_state in ['sent', 'sent_modified']:
            self.cancel_sii()

    @api.model
    def _check_default_ac_analytic_id(self):
        if self.journal_id:
            if self.journal_id and self.journal_id.code == 'CANJE':
                if not self.default_ac_analytic_id:
                    raise ValidationError(
                        "En los diarios de CANJE es obligatoria la cuenta analítica en la factura. No se admite por línea.")

    @api.model
    def create(self, vals):
        invoice = super(AccountInvoice, self).create(vals)
        invoice._check_default_ac_analytic_id()
        if invoice.invoice_line_ids and invoice.type in ['in_refund', 'in_invoice']:
            for invoice_line in invoice.invoice_line_ids:
                if not invoice_line.account_analytic_id and invoice.default_ac_analytic_id:
                    invoice_line.write({'account_analytic_id': invoice.default_ac_analytic_id.id})
                if invoice.type in ['in_invoice', 'in_refund']:
                    if not invoice_line.product_id.supplier_taxes_id:
                        if invoice_line.invoice_line_tax_ids:
                            raise UserError(
                                "Para el producto {} el impuesto {} no está configurado".format(
                                    invoice_line.product_id.name, invoice_line.invoice_line_tax_ids[0].name))
                        else:
                            raise UserError(
                                "Para el producto {} no tiene impuestos configurados".format(
                                    invoice_line.product_id.name))

            for tax_line in invoice.tax_line_ids:
                if not tax_line.account_analytic_id and invoice.default_ac_analytic_id:
                    tax_line.write({'account_analytic_id': invoice.default_ac_analytic_id.id})

        if invoice.invoice_line_ids and invoice.type in ['out_refund', 'out_invoice']:
            for invoice_line in invoice.invoice_line_ids:
                if invoice.type in ['out_invoice', 'out_refund']:
                    if invoice.journal_id.code == 'CANJE' and not invoice_line.account_analytic_id and invoice.default_ac_analytic_id:
                        invoice_line.write({'account_analytic_id': invoice.default_ac_analytic_id.id})
                    if not invoice_line.product_id.taxes_id:
                        if invoice_line.invoice_line_tax_ids:
                            raise UserError(
                                "Para el producto {} el impuesto {} no está configurado".format(
                                    invoice_line.product_id.name, invoice_line.invoice_line_tax_ids[0].name))
                        else:
                            raise UserError(
                                "Para el producto {} no tiene impuestos configurados".format(
                                    invoice_line.product_id.name))

        if invoice.move_id:
            invoice._remove_move_if_must_and_exists()
        return invoice

    @api.multi
    def _remove_move_if_must_and_exists(self):
        self.ensure_one()
        account_journal_cnj = self.env['account.journal'].search([('code', '=', 'CANJE')], limit=1)
        if self.move_id and account_journal_cnj and self.journal_id.id == account_journal_cnj.id and self.move_id.state not in [
            'posted']:
            number = self.number
            #self.move_id = [(2, self.move_id.id, False)]
            self.move_id.create_lines_cnj()
            self.write({
                'number': number,
                'state': 'paid',
                'residual': 0
            })
            payment_term_id_pay = self.env['ir.property'].sudo().search([('name', '=', 'payment_term_id_pay')])
            payment_term_id_pay = payment_term_id_pay.value_reference.split(',')
            payment_term_id_pay = int(payment_term_id_pay[1])
            payment_term_id_pay = self.env['account.payment.term'].search([('id', '=', payment_term_id_pay)])
            self.write({
                'payment_term_id': payment_term_id_pay.id
            })
    @api.multi
    def generate_payment_by_method(self):
        """
        Este método calcula los pagos para las facturas de KFC en proporción a sus métodos de pago
        y los concilia con las facturas
        :return:
        """
        data = {}
        # Recorremos las facturas
        for inv in self:
            # Si no tiene lineas la factura omitimos el pago
            if not inv.invoice_line_ids:
                continue
            # Si no tiene fecha de venta (no es de ventas KFC o no está correctamente generada) omitimos el pago
            if not inv.real_sale_date:
                continue
            # Obtenemos la tienda a partir del partner_id
            store_id = self.env['chariots.import.kfc.store'].search([('partner_id', '=', inv.partner_id.id)])
            # Si no hay una tienda asociada omitimos el pago
            if not store_id:
                raise ValidationError("Falta crear la tienda a {}".format(inv.partner_id.name))
            # Si la factura ya tiene un asiento de pago lo eliminamos
            if inv.move_payment_id:
                #inv.move_payment_id = [(2, inv.move_payment_id.id, False)]
                self._cr.execute("""
                    UPDATE account_invoice SET move_payment_id = NULL WHERE id = {};
                    DELETE FROM account_move_line where move_id = {};
                    DELETE FROM account_move WHERE id = {};
                """.format(inv.id, inv.move_payment_id.id, inv.move_payment_id.id))
                self._cr.commit()
            
            journal_payment_kfc = self.env['account.journal'].search([('code', '=', 'PAYKFC')])
            if not journal_payment_kfc:
                raise ValidationError("Falta crear el diario de Pagos KFC")
            
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
            amount_total_total = 0
            if not results:
                # Si no devuelve resultados la consulta SQL omitimos el pago
                logging.info("No existen resultados para la factura {}".format(inv.id))
                raise ValidationError("No hay metodos de pago  establecidos para la factura {}".format(inv.partner_id.number))
                continue
            # Recorremos las líneas de pago de KFC
            for payment_method_id, payment_method_name, amount_total_fix in results:
                if not payment_method_id:
                    logging.info("No existen método de pago para la factura {}".format(inv.id))
                    continue
                amount_total_total += amount_total_fix
                if payment_method_id not in data:
                    journal_payment = self.env['chariots.import.kfc.paymethod'].search(
                        [('id', '=', payment_method_id)])

                    if not journal_payment.account_id:
                        raise ValidationError(
                            "Falta cuenta contable para el Método de Pago con ID {} ".format(
                                journal_payment.external_id))

                    data[payment_method_id] = {
                        'name': payment_method_name,
                        'total': amount_total_fix,
                        'journal_id': journal_payment.journal_id.id,
                        'account_id': journal_payment.account_id.id
                    }
                else:
                    data[payment_method_id]['total'] += amount_total_fix
            if not data:
                logging.info("No existen datos para la factura {}".format(inv.id))
                continue
            move_vals = {}
            move_lines = []
            for dat in data: 
                if data[dat]['account_id'] and data[dat]['journal_id']:
                    move_line_vals = {
                        'partner_id': inv.partner_id.id,
                        'account_id': data[dat]['account_id'],
                        'name': data[dat]['name'],
                        'date_maturity': inv.date_due,
                        'debit': data[dat]['total'],
                        'credit': 0,
                        'analytic_account_id': inv.default_ac_analytic_id.id
                    }
                    move_lines.append((0, 0, move_line_vals))
            if move_lines:
                move_line_vals = {
                    'partner_id': inv.partner_id.id,
                    'account_id': inv.account_id.id,
                    'date_maturity': inv.date_due,
                    'debit': 0,
                    'credit': amount_total_total,
                    'analytic_account_id': inv.default_ac_analytic_id.id

                }
                move_lines.append((0, 0, move_line_vals))
                move_vals = {
                    'line_ids': move_lines,
                    'date': inv.date_invoice,
                    'move_type': 'payable',
                    'journal_id': journal_payment_kfc.id,
                    'default_account_analytic': inv.default_ac_analytic_id.id,
                    'is_unique_analytic': True,
                    'company_id': inv.company_id.id
                }
                new_move = self.env['account.move'].with_context(not_check_analytic_balance=True).create(move_vals)
                if new_move:
                    new_move.mapped('line_ids').create_analytic_lines()
                    self.env.cr.execute("""
                        UPDATE account_invoice	
                        SET move_payment_id = {}	
                        WHERE id = {}
                        """.format(new_move.id, inv.id))
                    self.env.cr.commit()

    @api.multi
    def write(self, vals):
        result = True
        context = dict(self.env.context)
        
        for invoice in self:
            result = result and super(AccountInvoice, invoice).write(vals)
            invoice._check_default_ac_analytic_id()
            if invoice.invoice_line_ids and invoice.type in ['in_refund', 'in_invoice']:
                for invoice_line in invoice.invoice_line_ids:
                    if not invoice_line.account_analytic_id and invoice.default_ac_analytic_id:
                        invoice_line.write({'account_analytic_id': invoice.default_ac_analytic_id.id})
                    if invoice.type in ['in_invoice', 'in_refund']:
                        if not invoice_line.product_id.supplier_taxes_id:
                            if invoice_line.invoice_line_tax_ids:
                                raise UserError(
                                    "Para el producto {} el impuesto {} no está configurado".format(
                                        invoice_line.product_id.name, invoice_line.invoice_line_tax_ids[0].name))
                            else:
                                raise UserError(
                                    "Para el producto {} no tiene impuestos configurados".format(
                                        invoice_line.product_id.name))
                    if not context.get('partner_required', False):
                        if not invoice.partner_id:
                            raise UserError("Proveedor no establecido")

                for tax_line in invoice.tax_line_ids:
                    if not tax_line.account_analytic_id and invoice.default_ac_analytic_id:
                        tax_line.write({'account_analytic_id': invoice.default_ac_analytic_id.id})
            if invoice.invoice_line_ids and invoice.type in ['out_refund', 'out_invoice']:
                for invoice_line in invoice.invoice_line_ids:
                    if invoice.type in ['out_invoice', 'out_refund']:
                        if invoice.journal_id.code == 'CANJE' and not invoice_line.account_analytic_id and invoice.default_ac_analytic_id:
                            invoice_line.write({'account_analytic_id': invoice.default_ac_analytic_id.id})
                        if not invoice_line.product_id.taxes_id:
                            if invoice_line.invoice_line_tax_ids:
                                raise UserError(
                                    "Para el producto {} el impuesto {} no está configurado".format(
                                        invoice_line.product_id.name, invoice_line.invoice_line_tax_ids[0].name))
                            else:
                                if invoice_line.product_id:
                                    raise UserError(
                                        "Para el producto {} no tiene impuestos configurados".format(
                                            invoice_line.product_id.name))
            if invoice.state == 'paid':
                if invoice.is_flagged:
                    invoice.is_flagged = False
            #if invoice.move_id:
                #invoice._remove_move_if_must_and_exists()
        return result

    @api.multi
    def map_sii_tax_template(self, tax_template, mapping_taxes):
        """Adds a tax template -> tax id to the mapping.
        Adapted from account_chart_update module.

        :param self: Single invoice record.
        :param tax_template: Tax template record.
        :param mapping_taxes: Dictionary with all the tax templates mapping.
        :return: Tax template current mapping
        """
        self.ensure_one()
        if not tax_template:
            return self.env['account.tax']
        if mapping_taxes.get(tax_template):
            return mapping_taxes[tax_template]
        # search inactive taxes too, to avoid re-creating
        # taxes that have been deactivated before
        tax_obj = self.env['account.tax'].with_context(active_test=False)
        criteria = [
            '|', '|',
            ('name', '=', tax_template.name),
            ('description', '=', tax_template.name),
            ('tax_template_id', '=', tax_template.id)
        ]
        if tax_template.description:
            criteria = ['|'] + criteria
            criteria += [
                '|',
                ('description', '=', tax_template.description),
                ('name', '=', tax_template.description),
            ]
        criteria += [('company_id', '=', self.company_id.id)]
        mapping_taxes[tax_template] = tax_obj.search(criteria)
        return mapping_taxes[tax_template]

    def _prepare_tax_line_vals(self, line, tax):
        vals = super(AccountInvoice, self)._prepare_tax_line_vals(line, tax)
        vals['analytic_tag_ids'] = False
        return vals

    @api.multi
    def update_move_lines(self):
        for inv in self:
            if inv.move_id.line_ids:
                continue
            company_currency = inv.company_id.currency_id

            # create move lines (one per invoice line + eventual taxes and analytic lines)
            iml = inv.invoice_line_move_line_get()
            iml += inv.tax_line_move_line_get()

            diff_currency = inv.currency_id != company_currency
            # create one move line for the total and possibly adjust the other lines amount
            total, total_currency, iml = inv.compute_invoice_totals(company_currency, iml)

            name = inv.name or ''
            if inv.payment_term_id:
                totlines = \
                    inv.payment_term_id.with_context(currency_id=company_currency.id).compute(total, inv.date_invoice)[
                        0]
                res_amount_currency = total_currency
                for i, t in enumerate(totlines):
                    if inv.currency_id != company_currency:
                        amount_currency = company_currency._convert(
                            t[1],
                            inv.currency_id, inv.company_id,
                            inv._get_currency_rate_date() or fields.Date.today()
                        )
                    else:
                        amount_currency = False

                    # last line: add the diff
                    res_amount_currency -= amount_currency or 0
                    if i + 1 == len(totlines):
                        amount_currency += res_amount_currency

                    iml.append({
                        'type': 'dest',
                        'name': name,
                        'price': t[1],
                        'account_id': inv.account_id.id,
                        'date_maturity': t[0],
                        'amount_currency': diff_currency and amount_currency,
                        'currency_id': diff_currency and inv.currency_id.id,
                        'invoice_id': inv.id
                    })
            else:
                iml.append({
                    'type': 'dest',
                    'name': name,
                    'price': total,
                    'account_id': inv.account_id.id,
                    'date_maturity': inv.date_due,
                    'amount_currency': diff_currency and total_currency,
                    'currency_id': diff_currency and inv.currency_id.id,
                    'invoice_id': inv.id
                })
            part = self.env['res.partner']._find_accounting_partner(inv.partner_id)
            line = [(0, 0, self.line_get_convert(l, part.id)) for l in iml]
            line = inv.group_lines(iml, line)

            line = inv.finalize_invoice_move_lines(line)

            mov_id = inv.move_id
            mov_id.write({'line_ids': line})

    def cron_rebuild_moves(self):
        invoices = self.env[self._name].search([
            ('residual', '=', 0),
            ('state', '=', 'open')
        ])
        for inv in invoices:
            move = inv.move_id
            if move.state != 'draft' or move.amount != 0:
                continue
            inv.move_id = False
            move.unlink()
            inv.action_move_create()

    @api.multi
    def invoices_flag(self, flag):
        group_manager = self.env.ref('account.group_account_manager')
        if group_manager.id not in self.env.user.groups_id.ids:
            raise ValidationError("No tienes permisos para utilizar esta acción")
        for invoice in self:
            if flag:
                invoice.write({'is_flagged': False})
            else:
                invoice.write({'is_flagged': True})

    @api.onchange('reference', 'partner_id')
    def _onchange_reference_partner(self):
        for inv in self:
            if inv.type not in ['in_invoice', 'in_refund']:
                continue
            if not inv.reference or not inv.partner_id:
                continue
            invoices = self.env[self._name].search([
                ('partner_id', '=', inv.partner_id.id),
                ('reference', '=', inv.reference)
            ])
            if invoices:
                return {
                    'warning': {
                        'title': "Referencia Duplicada",
                        'message': "Esta referencia de la factura ya existe para este proveedor"
                    }
                }

            if inv.expense_ids and inv.type in ['in_invoice'] and inv.partner_id and inv.reference:
                ir_attachment_obj = self.env['ir.attachment']
                identi = ''
                if not isinstance(inv.id, int):
                    identi = self._origin.id
                else:
                    identi = inv.id

                for expense in inv.expense_ids:
                    attachment = ir_attachment_obj.search([
                        ('res_id','=', identi),
                        ('type','=', 'binary'),
                        ('res_model', '=', 'account.invoice'),
                        ('name', '=', (inv.partner_id.ref + '_' + inv.reference + '.pdf'))
                    ])
                    if attachment:
                        for attach in attachment:
                            attach.unlink()

                    attachment = ir_attachment_obj.search([
                        ('res_id','=', expense.id),
                        ('type','=', 'binary'),
                        ('res_model','=', 'hr.expense')
                    ])
                    if attachment and identi > 0:
                        values = {
                            'name': inv.partner_id.ref + '_' + inv.reference + '.pdf',
                            'res_model': 'account.invoice',
                            'res_id': identi,
                            'type': 'binary',
                            'datas_fname': inv.partner_id.ref + '_' + inv.reference + '.pdf',
                            'datas': attachment.datas
                        }
                        new_attachment = ir_attachment_obj.create(values)

    @api.model
    def invoice_line_move_line_get(self):
        res = []
        account_one = self.env['ir.property'].sudo().search([('name', '=', 'account_account_donative_one')])
        account_one = account_one.value_reference.split(',')
        account_one = int(account_one[1])
        account_one = self.env['account.account'].search([('id', '=', account_one)])
        account_two = self.env['ir.property'].sudo().search([('name', '=', 'account_account_donative_two')])
        account_two = account_two.value_reference.split(',')
        account_two = int(account_two[1])
        account_two = self.env['account.account'].search([('id', '=', account_two)])
        dict_line_account_one = {}
        dict_line_account_two = {}
        for line in self.invoice_line_ids:
            if not line.account_id:
                continue
            if line.quantity == 0:
                continue
            tax_ids = []
            for tax in line.invoice_line_tax_ids:
                if tax.amount == 0:
                    if account_one:
                        if not dict_line_account_one:
                            dict_line_account_one = {
                                'type': 'src',
                                'name': 'DONATIVOS',
                                'price_unit': line.price_unit,
                                'quantity': 1,
                                'price': line.price_subtotal,
                                'account_id': account_one.id,
                                'uom_id': line.uom_id.id,
                                'account_analytic_id': line.account_analytic_id.id,
                                'tax_ids': [(4, tax.id, None)],
                                'invoice_id': self.id,
                            }
                        else:
                            dict_line_account_one.update(
                                {'price': (dict_line_account_one['price'] + line.price_subtotal)})

                    if account_two:
                        if not dict_line_account_two:
                            dict_line_account_two = {
                                'type': 'src',
                                'name': 'DONATIVOS',
                                'price_unit': line.price_unit,
                                'quantity': 1,
                                'price': line.price_subtotal * -1,
                                'account_id': account_two.id,
                                'uom_id': line.uom_id.id,
                                'account_analytic_id': line.account_analytic_id.id,
                                'tax_ids': [(4, tax.id, None)],
                                'invoice_id': self.id,
                            }
                        else:
                            dict_line_account_two.update(
                                {'price': (dict_line_account_two['price'] + (line.price_subtotal * -1))})

                tax_ids.append((4, tax.id, None))
                for child in tax.children_tax_ids:
                    if child.type_tax_use != 'none':
                        tax_ids.append((4, child.id, None))
            analytic_tag_ids = [(4, analytic_tag.id, None) for analytic_tag in line.analytic_tag_ids]

            move_line_dict = {
                'invl_id': line.id,
                'type': 'src',
                'name': line.name,
                'price_unit': line.price_unit,
                'quantity': line.quantity,
                'price': line.price_subtotal,
                'account_id': line.account_id.id,
                'product_id': line.product_id.id,
                'uom_id': line.uom_id.id,
                'account_analytic_id': line.account_analytic_id.id,
                'analytic_tag_ids': analytic_tag_ids,
                'tax_ids': tax_ids,
                'invoice_id': self.id,
            }
            res.append(move_line_dict)
        journal_kfc = self.env['ir.property'].sudo().search([('name', '=', 'account_journal_kfc_id')])
        journal_kfc = journal_kfc.value_reference.split(',')
        journal_kfc = int(journal_kfc[1])
        if journal_kfc:
            if self.journal_id.id == journal_kfc and dict_line_account_one and dict_line_account_two:
                res.append(dict_line_account_one)
                res.append(dict_line_account_two)

        return res

    @api.model
    def tax_line_move_line_get(self):
        res = []
        # keep track of taxes already processed
        done_taxes = []
        # loop the invoice.tax.line in reversal sequence
        for tax_line in sorted(self.tax_line_ids, key=lambda x: -x.sequence):
            tax = tax_line.tax_id
            if tax.amount_type == "group":
                for child_tax in tax.children_tax_ids:
                    done_taxes.append(child_tax.id)

            analytic_tag_ids = [(4, analytic_tag.id, None) for analytic_tag in tax_line.analytic_tag_ids]
            res.append({
                'invoice_tax_line_id': tax_line.id,
                'tax_line_id': tax_line.tax_id.id,
                'type': 'tax',
                'name': tax_line.name,
                'price_unit': tax_line.amount_total,
                'quantity': 1,
                'price': tax_line.amount_total,
                'account_id': tax_line.account_id.id,
                'account_analytic_id': tax_line.account_analytic_id.id,
                'analytic_tag_ids': analytic_tag_ids,
                'invoice_id': self.id,
                'tax_ids': []
            })
            done_taxes.append(tax.id)
        return res

    @api.multi
    def upload_file_inv_drive(self):
        self.ensure_one()
        att_obj = self.env['ir.attachment']
        attachs_del = att_obj.search([
            ('res_id', '=', self.id),
            ('cloud_path', 'ilike', "Facturas por Centro"),
            ('cloud_key', '!=', False)
        ])
        for att in attachs_del:
            res = att.delete_file_inv()
            if res:
                att.unlink()

        attach = att_obj.search([
            ('res_id', '=', self.id),
            ('type', '=', 'url'),
            ('cloud_key', '!=', False),
        ])
        in_folder = False
        if len(attach) > 1:
            in_folder = True
        res = att_obj.upload_file_inv(self.id, in_folder)
        
        for att in attach:
            att.send_at_cloud(res['key'], self.reference)
    

    @api.model
    def _prepare_refund(self, invoice, date_invoice=None, date=None, description=None, journal_id=None):
        """ Prepare the dict of values to create the new credit note from the invoice.
            This method may be overridden to implement custom
            credit note generation (making sure to call super() to establish
            a clean extension chain).

            :param record invoice: invoice as credit note
            :param string date_invoice: credit note creation date from the wizard
            :param integer date: force date from the wizard
            :param string description: description of the credit note from the wizard
            :param integer journal_id: account.journal from the wizard
            :return: dict of value to create() the credit note
        """
        values = {}
        for field in self._get_refund_copy_fields():
            if invoice._fields[field].type == 'many2one':
                values[field] = invoice[field].id
            else:
                values[field] = invoice[field] or False

        values['invoice_line_ids'] = self._refund_cleanup_lines(invoice.invoice_line_ids)

        tax_lines = invoice.tax_line_ids
        taxes_to_change = {
            line.tax_id.id: line.tax_id.refund_account_id.id
            for line in tax_lines.filtered(lambda l: l.tax_id.refund_account_id != l.tax_id.account_id)
        }
        cleaned_tax_lines = self._refund_cleanup_lines(tax_lines)
        values['tax_line_ids'] = self._refund_tax_lines_account_change(cleaned_tax_lines, taxes_to_change)

        if journal_id:
            journal = self.env['account.journal'].browse(journal_id)
        elif invoice['type'] == 'in_invoice':
            journal = self.env['account.journal'].search([('type', '=', 'purchase')], limit=1)
        else:
            journal = self.env['account.journal'].search([('type', '=', 'sale')], limit=1)
        values['journal_id'] = journal.id

        values['type'] = TYPE2REFUND[invoice['type']]
        values['date_invoice'] = date_invoice or fields.Date.context_today(invoice)
        values['date_due'] = values['date_invoice']
        values['state'] = 'draft'
        values['number'] = False
        values['origin'] = invoice.number
        values['payment_term_id'] = False
        values['refund_invoice_id'] = invoice.id

        if values['type'] == 'in_refund':
            partner_bank_result = self._get_partner_bank_id(values['company_id'])
            if partner_bank_result:
                values['partner_bank_id'] = partner_bank_result.id

        if date:
            values['date'] = date
        if description:
            values['name'] = description
        if invoice.default_ac_analytic_id:
            values['default_ac_analytic_id'] = invoice.default_ac_analytic_id.id
        return values



class AccountInvoiceLine(models.Model):
    _inherit = "account.invoice.line"
    
    @api.one
    @api.depends('price_unit', 'discount', 'invoice_line_tax_ids', 'quantity',
        'product_id', 'invoice_id.partner_id', 'invoice_id.currency_id', 'invoice_id.company_id',
        'invoice_id.date_invoice', 'invoice_id.date')
    def _compute_price(self):
        if self.invoice_id.journal_id.code != 'INV':
            return super(AccountInvoiceLine, self)._compute_price()


    def _get_price_tax(self):
        for l in self:
            if l.invoice_id.journal_id.code != 'INV':
                l.price_tax = l.price_total - l.price_subtotal
                

class AccountInvoiceTax(models.Model):
    _inherit = "account.invoice.tax"

    @api.depends('amount', 'invoice_id.invoice_line_ids')
    def _compute_force_base(self):
        tax_grouped = {}
        for invoice in self.mapped('invoice_id'):
            tax_grouped[invoice.id] = invoice.get_taxes_values()
        for tax in self:
            tax.force_base = 0.0
            if tax.tax_id:
                for tx_val in tax_grouped[tax.invoice_id.id]:
                    tax_id = tax_grouped[tax.invoice_id.id][tx_val]['tax_id']
                    if tax_id == tax.tax_id.id:
                        tax.force_base = tax_grouped[tax.invoice_id.id][tx_val]['base']

    force_base = fields.Monetary(string='Force Base', compute='_compute_force_base')
    force_base_company = fields.Monetary(
        string='Force Base in company currency',
        compute="_compute_force_base_company",
    )

    @api.multi
    def _compute_force_base_company(self):
        for tax in self:
            if (tax.invoice_id.currency_id !=
                    tax.invoice_id.company_id.currency_id):
                currency = tax.invoice_id.currency_id.with_context(
                    date=tax.invoice_id.date_invoice,
                    company_id=tax.invoice_id.company_id.id)
                tax.force_base_company = currency.compute(
                    tax.force_base, tax.invoice_id.company_id.currency_id)
            else:
                tax.force_base_company = tax.force_base
