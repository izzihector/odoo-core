import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = "account.move"

    is_unique_analytic = fields.Boolean(
        string="Usar cuenta analítica por defecto",
        default=True
    )
    default_account_analytic = fields.Many2one(
        comodel_name="account.analytic.account",
        string="Cuenta Analítica por Defecto"
    )
    code_repeat = fields.Char(
        string="Código Repetido"
    )
    for_delete = fields.Boolean(
        string="Para borrar",
        default=False
    )

    @api.model
    def create(self, vals_list):
        res = super(AccountMove, self).create(vals_list)
        context = dict(self.env.context)
        if not context.get('not_check_analytic_balance', False):
            res._check_analytic_balance()
        return res

    @api.multi
    def write(self, vals):
        res = super(AccountMove, self).write(vals)
        context = dict(self.env.context)
        logging.info(vals)
        if not context.get('not_check_analytic_balance', False):
            self._check_analytic_balance()
        return res

    @api.multi
    def _check_analytic_balance(self):
        # Buscamos la cuenta 900 para poder corregir el balance analítico
        account_900 = self.env['account.account'].search([('code', '=', '9000-0000')], limit=1)
        # Definimos las clases de los items que vamos a usar
        acc_mv_line_obj = self.env['account.move.line']
        # Buscamos las cuentas que necesitaremos para el balanceo
        account_one = self.env['ir.property'].sudo().search([('name', '=', 'account_account_type_c')])
        account_one = account_one.value_reference.split(',')
        account_one = int(account_one[1])
        account_one = self.env['account.account.type'].search([('id', '=', account_one)])
        account_two = self.env['ir.property'].sudo().search([('name', '=', 'account_account_type_p')])
        account_two = account_two.value_reference.split(',')
        account_two = int(account_two[1])
        account_two = self.env['account.account.type'].search([('id', '=', account_two)])
        for move in self:
            # Busca una CA por defecto
            main_aac = move.default_account_analytic
            lines_to_fix = []
            aacs = {}
            total_aacs = {}
            total_debit = 0
            total_credit = 0
            # Recorre la líneas del asiento en busca del nº de CA y el total de cada una además de
            # guardar en lines_to_fix las líneas sin CA que tienen que ser resueltas
            for line in move.line_ids:
                if not line.analytic_account_id:
                    aac = False
                    if move.is_unique_analytic and main_aac:
                        # Si la línea no tiene CA pero el asiento contable tiene una CA por defecto entonces
                        # la asignamos
                        line.analytic_account_id = main_aac
                        aac = main_aac
                    else:
                        # Si la línea no tiene CA y el asiento no tiene CA por defecto: tenemos que resolverla
                        lines_to_fix.append(line)
                else:
                    # Si la línea tiene CA está correcto
                    aac = line.analytic_account_id
                if not aac:
                    continue
                # Suma los debit y credit de cada CA para usarlo después en caso de ser necesario
                if aac.id not in aacs:
                    aacs[aac.id] = line.analytic_account_id
                    total_aacs[aac.id] = {
                        'debit': 0,
                        'credit': 0
                    }
                total_aacs[aac.id]['debit'] += line.debit
                total_aacs[aac.id]['credit'] += line.credit
                total_debit += line.debit
                total_credit += line.credit

            total_to_fix = len(lines_to_fix)
            aac_list = aacs.values()
            total_aac = len(aac_list)
            if total_to_fix > 0 and total_aac == 1:
                # Si hay más de una línea por solucionar y el asiento solo tiene una CA entonces asignamos a
                # las líneas vacías esta CA
                for line in lines_to_fix:
                    for ac in aac_list:
                        line.analytic_account_id = ac
            elif total_to_fix > 0 and total_aac == 0:
                # Si ninguna de las líneas del asiento tiene una CA lanzamos error
                raise UserError("""
                    1- No se puede crear un asiento con líneas sin cuentas analíticas.
                    A excepción de un asiento con una cuenta analítica por defecto
                """)
            elif total_to_fix > 1 and total_aac > 1:
                # Si hay más de una línea sin CA y el resto de líneas tiene más de una CA lanzamos error
                raise UserError("""
                    1- No se puede crear un asiento con líneas con más de una cuenta analítica y líneas sin cuenta analítica
                """)
            elif total_to_fix == 1 and total_aac > 1:
                # Si hay solo una línea pendiente de solucionar pero hay más de una cuenta analítica en el asiento
                # Tenemos que dividir esta línea en tantas líneas como CAs existan
                # TODO: Pendiente de revisar porque entra en bucle
                line = lines_to_fix[0]
                if line.user_type_id and account_one and account_two:
                    if line.user_type_id.id not in [account_one.id, account_two.id]:
                        continue
                update_lines = []
                i = 1
                residual_debit = 0
                residual_credit = 0
                for aac in aac_list:
                    total_debit_aac = total_aacs[aac.id]['debit']
                    if total_debit:
                        perc_debit = total_debit_aac / total_debit
                    else:
                        perc_debit = 0
                    total_credit_aac = total_aacs[aac.id]['credit']
                    if total_credit:
                        perc_credit = total_credit_aac / total_credit
                    else:
                        perc_credit = 0
                    debit_raw = line.debit * perc_credit
                    debit = round(debit_raw, 4)
                    residual_debit += (debit_raw - debit)
                    credit_raw = line.credit * perc_debit
                    credit = round(credit_raw, 4)
                    residual_credit += (credit_raw - credit)
                    if i == 1:
                        update_lines.append((1, line.id, {
                            'debit': debit,
                            'credit': credit,
                            'analytic_account_id': aac.id,
                        }))
                        i += 1
                        continue
                    i += 1
                    if i == total_aac:
                        debit += round(residual_debit, 4)
                        credit += round(residual_credit, 4)
                    update_lines.append((0, 0, {
                        'treasury_date': line.treasury_date,
                        'treasury_planning': line.treasury_planning,
                        'forecast_id': line.forecast_id.id if line.forecast_id else False,
                        'move_id': line.move_id.id,
                        'company_id': line.company_id.id if line.company_id else False,
                        'expense_id': line.expense_id.id if line.expense_id else False,
                        'invoice_id': line.invoice_id.id if line.invoice_id else False,
                        'statement_id': line.statement_id.id if line.statement_id else False,
                        'statement_line_id': line.statement_line_id.id if line.statement_line_id else False,
                        'name': line.name,
                        'analytic_account_id': aac.id,
                        'credit': credit,
                        'debit': debit,
                        'partner_id': line.partner_id.id,
                        'account_id': line.account_id.id
                    }))
                move.with_context(not_check_analytic_balance=True).write({
                    'line_ids': update_lines
                })
                continue

            totals = {}
            # Suma los balances (debit-credit) de las CAs para comprobar cuales hay que solucionar
            for line in move.line_ids:
                key = line.analytic_account_id.id
                if key not in totals:
                    totals[key] = {
                        'balance': 0.0,
                        'credit': 0.0,
                        'debit': 0.0,
                        'account': line.analytic_account_id,
                        'line': line,
                        'lines': []
                    }
                totals[key]['credit'] += line.credit
                totals[key]['debit'] += line.debit
                totals[key]['balance'] = abs(totals[key]['debit'] - totals[key]['credit'])
                totals[key]['lines'].append(line)
            total_list = totals.values()
            if not account_900:
                raise UserError("No hay una cuenta para equilibrar cuentas analíticas. Debe tener el código 9000-0000")
            new_lines = []
            for total in total_list:
                if total['balance'] > 0.001:
                    # Si hay una diferencia mayor a 0.001 entonces tenemos que ajustar la CA
                    # TODO: Pendiente de revisar porque entra en bucle
                    line = total['line']
                    new_value = {
                        'treasury_date': line.treasury_date,
                        'treasury_planning': line.treasury_planning,
                        'move_id': line.move_id.id,
                        'company_id': line.company_id.id if line.company_id else False,
                        'expense_id': line.expense_id.id if line.expense_id else False,
                        'forecast_id': line.forecast_id.id if line.forecast_id else False,
                        'invoice_id': line.invoice_id.id if line.invoice_id else False,
                        'statement_id': line.statement_id.id if line.statement_id else False,
                        'statement_line_id': line.statement_line_id.id if line.statement_line_id else False,
                        'name': 'Balance Analítico',
                        'analytic_account_id': total['account'].id,
                        'credit': 0.0,
                        'debit': 0.0,
                        'partner_id': False,
                        'account_id': account_900.id
                    }
                    debit_value = new_value.copy()
                    credit_value = new_value.copy()
                    if total['debit'] > 0.0 or total['debit'] < 0.0:
                        debit_value['credit'] = total['debit']
                        new_lines.append((0, 0, debit_value))
                    if total['credit'] > 0.0 or total['credit'] < 0.0:
                        credit_value['debit'] = total['credit']
                        new_lines.append((0, 0, credit_value))
            if len(new_lines) > 0:
                move.with_context(not_check_analytic_balance=True).write({
                    'line_ids': new_lines
                })

    @api.multi
    def assert_balanced(self):
        context = dict(self.env.context)
        if context.get('tracking_disable'):
            return True
        if not context.get('not_check_analytic_balance', False):
            return super(AccountMove, self).assert_balanced()
        return True

    @api.multi
    def post(self, invoice=False):
        self._post_validate()
        self.assert_balanced()
        # Create the analytic lines in batch is faster as it leads to less cache invalidation.
        self.mapped('line_ids').create_analytic_lines()
        for move in self:
            if move.name == '/':
                new_name = False
                journal = move.journal_id

                if invoice and invoice.move_name and invoice.move_name != '/':
                    new_name = invoice.move_name
                else:
                    if journal.sequence_id:
                        # If invoice is actually refund and journal has a refund_sequence then use that one or use the regular one
                        sequence = journal.sequence_id
                        if invoice and invoice.type in ['out_refund', 'in_refund'] and journal.refund_sequence:
                            if not journal.refund_sequence_id:
                                raise UserError(_('Please define a sequence for the credit notes'))
                            sequence = journal.refund_sequence_id

                        new_name = sequence.with_context(ir_sequence_date=move.date).next_by_id()
                    else:
                        raise UserError(_('Please define a sequence on the journal.'))

                if new_name:
                    move.name = new_name
                if invoice:
                    if invoice.default_ac_analytic_id:
                        move.default_account_analytic = invoice.default_ac_analytic_id
                    else:
                        if move.line_ids:
                            line_ids = move.line_ids.filtered(lambda line: not line.analytic_account_id)
                            move.create_new_analytic_lines(invoice, line_ids)

            if move == move.company_id.account_opening_move_id and not move.company_id.account_bank_reconciliation_start:
                # For opening moves, we set the reconciliation date threshold
                # to the move's date if it wasn't already set (we don't want
                # to have to reconcile all the older payments -made before
                # installing Accounting- with bank statements)
                move.company_id.account_bank_reconciliation_start = move.date

        if (invoice and invoice.is_assess) or not invoice:
            return self.write({'state': 'posted'})

        return self.write({'state': 'draft'})

    def create_new_analytic_lines(self, invoice, line_ids):
        for line in line_ids:
            lines_account = []
            if line.tax_line_id:
                invoice_line_ids = invoice.invoice_line_ids.filtered(
                    lambda inv_line: line.tax_line_id.id in inv_line.invoice_line_tax_ids.ids)
                if invoice_line_ids:
                    for inv_line in invoice_line_ids:
                        if not inv_line.account_analytic_id:
                            continue
                        line_analytics = ''
                        if line.analytic_line_ids:
                            line_analytics = line.analytic_line_ids.filtered(
                                lambda l: l.account_id.id == inv_line.account_analytic_id.id)
                        if line_analytics:
                            continue
                        cant = 1
                        imp = 0
                        if line.debit > 0:
                            imp = inv_line.price_tax * -1
                        else:
                            imp = inv_line.price_tax

                        dict_create = {
                            'name': line.name,
                            'ref': line.move_id.ref if line.move_id else '',
                            'partner_id': line.partner_id.id if line.partner_id else False,
                            'date': line.date,
                            'company_id': line.move_id.company_id.id,
                            'general_account_id': line.account_id.id,
                            'unit_amount': cant,
                            'amount': imp,
                            'account_id': inv_line.account_analytic_id.id,
                            'product_id': inv_line.product_id.id,
                            'product_uom_id': inv_line.uom_id.id,
                        }
                        lines_account.append((0, 0, dict_create))
            else:
                if not line.tax_line_id and not line.name:
                    invoice_line_ids = invoice.invoice_line_ids
                    if invoice_line_ids:
                        for inv_line in invoice_line_ids:
                            if not inv_line.account_analytic_id:
                                continue
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
                                'name': inv_line.product_id.name,
                                'ref': line.move_id.ref if line.move_id else '',
                                'partner_id': line.partner_id.id if line.partner_id else False,
                                'date': line.date,
                                'company_id': line.move_id.company_id.id,
                                'general_account_id': line.account_id.id,
                                'unit_amount': cant,
                                'amount': imp,
                                'account_id': inv_line.account_analytic_id.id,
                                'product_id': inv_line.product_id.id,
                                'product_uom_id': inv_line.uom_id.id,
                            }
                            lines_account.append((0, 0, dict_create))
            if lines_account:
                line.write({'analytic_line_ids': lines_account})

    @api.multi
    def create_lines_cnj(self):
        self.ensure_one()
        account_journal_cnj = self.env['account.journal'].search([('code', '=', 'CANJE')], limit=1)
        if self.journal_id and account_journal_cnj and self.journal_id.id == account_journal_cnj.id:
            if self.line_ids:
                new_lines = []
                for line in self.line_ids:
                    tax_ids = []
                    if line.tax_ids:
                        tax_ids = [x.id for x in line.tax_ids]
                    dict_update = {
                        'treasury_date': line.treasury_date,
                        'treasury_planning': line.treasury_planning,
                        'move_id': line.move_id.id,
                        'company_id': line.company_id.id if line.company_id else False,
                        'expense_id': line.expense_id.id if line.expense_id else False,
                        'forecast_id': line.forecast_id.id if line.forecast_id else False,
                        'invoice_id': line.invoice_id.id if line.invoice_id else False,
                        'statement_id': line.statement_id.id if line.statement_id else False,
                        'statement_line_id': line.statement_line_id.id if line.statement_line_id else False,
                        'name': line.name,
                        'analytic_account_id': line.analytic_account_id.id if line.analytic_account_id else False,
                        'credit': 0.0,
                        'debit': 0.0,
                        'partner_id': line.partner_id.id if line.partner_id else False,
                        'tax_line_id': line.tax_line_id.id if line.tax_line_id else False,
                        'account_id': line.account_id.id,
                        'tax_ids': [(6, 0, tax_ids)] if tax_ids else [],
                        'tax_base_amount': line.tax_base_amount,

                    }
                    if line.debit > 0 or line.debit < 0:
                        dict_update['credit'] = line.debit
                        dict_update['debit'] = 0
                        new_lines.append((0, 0, dict_update))
                    if line.credit > 0 or line.credit < 0:
                        dict_update['credit'] = 0
                        dict_update['debit'] = line.credit
                        new_lines.append((0, 0, dict_update))
                if new_lines:
                    self.write({'line_ids': new_lines})


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    @api.model
    def cron_balance_analytic(self):
        aml_obj = self.env[self._name].sudo()
        acc_pay_obj = self.env['account.payment']
        line_without_aac = aml_obj.search([
            ('company_id', '=', 1),
            ('analytic_account_id', '=', False)
        ])
        total_without_aac = 0
        total_morethanone_aac = 0

        for line in line_without_aac:
            able_to_aac_dict = {}
            for aml in line.move_id.line_ids:
                if aml.analytic_account_id:
                    able_to_aac_dict[aml.analytic_account_id.id] = aml.analytic_account_id
            able_to_aac_ids = able_to_aac_dict.values()
            len_able_to_aac_ids = len(able_to_aac_ids)
            aac_id = False
            if len_able_to_aac_ids <= 0:
                # TODO: Si el resto de líneas del asiento no tienen cuenta analítica
                # 1. Si el asiento es de un pago de factura. Comprobamos su factura y si esta tiene una sola cuenta
                # analítica entonces asociamos esa cuenta analítica a este asiento
                # 2. Si el asiento es de banco y tiene un pago conciliado. Buscamos el pago:
                #  2.1 Si el pago tiene CA entonces se la asociamos
                #  2.2 Si el pago no tiene CA buscamos la factura del pago y asignamos esta CA
                # 3 Si el asiento proviene de un gasto y solo tiene una CA se la asignamos
                # 4 Si el asiento no tiene ninguna cuenta analitica pero una de las lineas tiene una etiqueta analítica
                # y esa etiqueta tiene distribucion analítica establecida y distribuciones analíticas asociadas
                logging.info("No existen cuentas analíticas para el asiento {}".format(line.move_id.id))
                aac_id = False
                payment = acc_pay_obj.search([('move_line_ids', 'in', line.id)])
                # Si es de un pago
                if payment:
                    invoice_id = False
                    # Comprobamos si viene de una factura

                    if payment.invoice_ids:
                        invoice_ids = payment.invoice_ids
                        if len(invoice_ids) == 1:
                            invoice_id = invoice_ids[0]
                    else:
                        if payment.reconciled_invoice_ids:
                            invoice_ids = payment.reconciled_invoice_ids
                            if len(invoice_ids) == 1:
                                invoice_id = invoice_ids[0]

                    if not invoice_id:
                        # Si viene de un extracto y no hay factura asignda al pago
                        if line.statement_line_id and line.statement_id and payment.state == 'reconciled':
                            lines_acc = line.move_id.line_ids.filtered(lambda x: x.analytic_account_id != False)
                            if lines_acc:
                                line_acc = lines_acc[0]
                                aac_id = line_acc.analytic_account_id
                    else:
                        if invoice_id.default_ac_analytic_id:
                            aac_id = invoice_id.default_ac_analytic_id
                        else:
                            logging.info("La factura {} tiene varias CAs".format(invoice_id.id))

                # Si es de un gasto
                if not payment and line.expense_id:
                    expense_id = line.expense_id
                    if expense_id.analytic_account_id:
                        aac_id = expense_id.analytic_account_id
                
                # Distribucion analítica
                if not aac_id:
                    # Si tiene etiquetas analiticas con distribucion analitica creamos apuntes nuevos y borramos este apunte
                    if not line.analytic_tag_ids:
                        continue

                    tag_ids = line.analytic_tag_ids.filtered(lambda x: x.active_analytic_distribution and x.analytic_distribution_ids)
                    if not tag_ids:
                        continue
                    line.create_analytic_distribution()

                total_without_aac += 1

            elif len_able_to_aac_ids > 1:
                # TODO: Si el resto de líneas del asiento tienen más de una cuenta analítica
                # 1 - Distribucion analitica
                # TODO Necesitamos saber el resto de casos con mas de una CA en el asiento
                logging.info("Existe más de una cuenta analítica para el asiento {}".format(line.move_id.id))
                aac_id = False
                total_morethanone_aac += 1
                
                # Si tiene etiquetas analiticas con distribucion analitica creamos apuntes nuevos y borramos este apunte
                if not line.analytic_tag_ids:
                    continue

                tag_ids = line.analytic_tag_ids.filtered(lambda x: x.active_analytic_distribution and x.analytic_distribution_ids)
                if not tag_ids:
                    continue
                #line.create_analytic_distribution()
            else:
                for aac_id in able_to_aac_ids:
                    aac_id = aac_id

            if aac_id:
                line.write({
                    'analytic_account_id': aac_id.id
                })
                self.env.cr.commit()
        logging.info("Apuntes que tengan asientos sin AAC: {}".format(total_without_aac))
        logging.info("Apuntes que tengan asientos con más de un AAC: {}".format(total_morethanone_aac))

    # Apuntes que estan con el diario de Pago de KFC
    def query_update_mv_lines_pay_kfc(self):
        self._cr.execute("""
            UPDATE account_move_line as mv_l SET
            analytic_account_id = res.default_ac_analytic_id 
            FROM (SELECT inv.default_ac_analytic_id as default_ac_analytic_id, inv.move_payment_id as move_id
                FROM account_invoice as inv
                WHERE inv.move_payment_id is not NULL and inv.default_ac_analytic_id is not NULL and inv.journal_id = 1 and date_invoice >= '2020-01-01') res
            WHERE mv_l.move_id = res.move_id and mv_l.journal_id = 53 and date >= '2020-01-01'
        """)
        self._cr.commit()
    
    @api.multi
    def create_analytic_distribution(self):
        for line in self:
            tag_ids = line.analytic_tag_ids.filtered(lambda x: x.active_analytic_distribution and x.analytic_distribution_ids)
            if not tag_ids:
                continue
            new_lines = []
            amount_total_debit = 0
            amount_total_credit = 0
            for tag_id in tag_ids:
                for distribution in tag_id.analytic_distribution_ids:
                    amount = line.balance * distribution.percentage / 100.0
                    tax_ids = []
                    if line.tax_ids:
                        tax_ids = [x.id for x in line.tax_ids]
                    dict_update = {
                        'treasury_date': line.treasury_date,
                        'treasury_planning': line.treasury_planning,
                        'move_id': line.move_id.id,
                        'company_id': line.company_id.id if line.company_id else False,
                        'expense_id': line.expense_id.id if line.expense_id else False,
                        'forecast_id': line.forecast_id.id if line.forecast_id else False,
                        'invoice_id': line.invoice_id.id if line.invoice_id else False,
                        'statement_id': line.statement_id.id if line.statement_id else False,
                        'statement_line_id': line.statement_line_id.id if line.statement_line_id else False,
                        'name': line.name,
                        'analytic_account_id': distribution.account_id.id if distribution.account_id else False,
                        'credit': 0.0,
                        'debit': 0.0,
                        'partner_id': line.partner_id.id if line.partner_id else False,
                        'tax_line_id': line.tax_line_id.id if line.tax_line_id else False,
                        'account_id': line.account_id.id,
                        'tax_ids': [(6, 0, tax_ids)] if tax_ids else [],
                        'tax_base_amount': line.tax_base_amount,

                    }
                    if not dict_update['analytic_account_id']:
                        continue
                    if line.debit > 0 or line.debit < 0:
                        dict_update['credit'] = 0
                        dict_update['debit'] = amount
                        amount_total_debit += amount
                        #line.debit = line.debit - amount
                        new_lines.append((0, 0, dict_update))
                        #new_line = self.env[self._name].create(dict_update)
                        #if new_line:
                            #new_line.create_analytic_lines()
                    if line.credit > 0 or line.credit < 0:
                        dict_update['credit'] = amount
                        dict_update['debit'] = 0
                        #line.credit = line.credit - amount
                        amount_total_credit += amount
                        new_lines.append((0, 0, dict_update))
                        """new_line = self.env[self._name].create(dict_update)
                        if new_line:
                            new_line.create_analytic_lines()"""
            if tag_ids and new_lines:
                if line.debit > 0 or line.debit < 0:
                    new_lines.append((1, line.id, {'debit': 0}))
                if line.credit > 0 or line.credit < 0:
                    new_lines.append((1, line.id, {'credit': 0}))
                
                move_id = line.move_id
                move_id.write({
                    'line_ids': new_lines
                })
                line.unlink()
           

    @api.model
    def create(self, vals_list):
        res = super(AccountMoveLine, self).create(vals_list)
        """if res.analytic_account_id:
            if res.analytic_tag_ids:
                res.create_analytic_distribution()"""
        return res
