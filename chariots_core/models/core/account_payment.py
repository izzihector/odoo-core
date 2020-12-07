# -*- coding: utf-8 -*-
import logging

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class account_payment(models.Model):
    _inherit = "account.payment"
    PUBLISH_STATES = ['posted']

    move_state = fields.Char(
        string="Estado de Asiento",
        compute="_compute_move_state",
        store=True
    )

    sequence = fields.Integer(
        string="Sequence",
        default=0
    )

    batch_payment_state = fields.Selection(
        string='Estado Lote De Pago',
        related='batch_payment_id.state'
    )
    batch_payment_count = fields.Integer(
        string="Nº Lotes de pago",
        compute="_compute_batch_payment",

    )

    @api.multi
    @api.depends('batch_payment_id')
    def _compute_batch_payment(self):
        for pay in self:
            count = 0
            if pay.batch_payment_id:
                count = 1
            pay.batch_payment_count = count

    @api.multi
    def action_view_batch_payment(self):
        self.ensure_one()
        action = {
            'name': _('Lote de pago'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.batch.payment',
            'target': 'current',
        }
        batch_payment_id = self.batch_payment_id.id
        if batch_payment_id:
            action['res_id'] = batch_payment_id
            action['view_mode'] = 'form'
        return action

    @api.multi
    @api.depends('move_line_ids')
    def _compute_move_state(self):
        for pay in self:
            if not pay.move_line_ids:
                continue
            pay.move_state = pay.move_line_ids[0].move_id.state

    @api.model
    def cron_to_publish(self):
        payments = self.env[self._name].sudo().search([])
        for payment in payments:
            payment.update({
                'state': 'draft'
            })
            if len(payment.move_line_ids.ids) > 0:
                payment.update({
                    'state': 'posted'
                })

    @api.model
    def create_batch_payment(self):
        batch = self.env['account.batch.payment'].create({
            'journal_id': self[0].journal_id.id,
            'payment_ids': [(4, payment.id, None) for payment in self],
            'payment_method_id': self[0].payment_method_id.id,
            'batch_type': self[0].payment_type,
        })

        return {
            "type": "ir.actions.act_window",
            "res_model": "account.batch.payment",
            "views": [[False, "form"]],
            "res_id": batch.id,
        }

    @api.multi
    def cancel_payments(self):
        group_manager = self.env.ref('account.group_account_manager')
        if group_manager.id not in self.env.user.groups_id.ids:
            raise ValidationError("No tienes permisos para cancelar los pagos")

        self.remove_concile_payment()
        self.cancel()
        for payment in self:
            if payment.state in self.PUBLISH_STATES:
                payment.write({
                    'state': 'cancelled',
                    '​invoice_ids': [(6, 0, 0)],
                    'move_state': False,
                    '​move_name': False,
                })
                payment.invoice_ids.write({
                    'is_flagged': True,
                })
                payment.reconciled_invoice_ids.write({
                    'is_flagged': True,
                })

    @api.multi
    def remove_concile_payment(self):
        for payment in self:
            if payment.move_line_ids:
                move_line_ids = payment.move_line_ids.filtered(
                    lambda x: x.full_reconcile_id != False)
                if move_line_ids:
                    for line in move_line_ids:
                        if line.full_reconcile_id or line.reconciled:
                            line.write({'reconciled': False, 'full_reconciled_id': False})

    @api.multi
    def unreconcile_payments(self):
        group_manager = self.env.ref('account.group_account_manager')
        if group_manager.id not in self.env.user.groups_id.ids:
            raise ValidationError("No tienes permisos para romper la conciliacion de los pagos")
        for payment in self:
            if payment.state == 'reconciled':
                if payment.move_line_ids:
                    move_line_ids = payment.move_line_ids.filtered(
                        lambda x: x.statement_line_id != False and x.move_id.state == 'posted')
                    if move_line_ids:
                        for line in move_line_ids:
                            if line.full_reconcile_id:
                                line.remove_move_reconcile()
                            line.write({'statement_line_id': ''})
                            if line.move_id.state == 'posted':
                                move_id = line.move_id
                                move_id.write({'state': 'draft', 'name': ''})
                        payment.write({'state': 'sent'})

    @api.multi
    def post(self):
        payment_method_id_sepa = self.env['account.payment.method'].search([('code', '=', 'sepa_ct')])
        for payment in self:
            if payment_method_id_sepa:
                if payment.state == 'draft' and not payment.partner_bank_account_id and payment.payment_method_id.id == payment_method_id_sepa.id:
                    raise ValidationError(
                        "No puedes publicar el pago {} ya que no tiene una cuenta bancaria asociada".format(
                            payment.name))
        super(account_payment, self).post()
        for payment in self:
            payment.invoice_ids.write({
                'is_flagged': False,
            })
            payment.reconciled_invoice_ids.write({
                'is_flagged': False,
            })

    def _get_liquidity_move_line_vals(self, amount):
        vals = super(account_payment, self)._get_liquidity_move_line_vals(amount=amount)
        context = dict(self.env.context)
        if context.get('force_payment_account_id', False):
            vals['account_id'] = context.get('force_payment_account_id')
        return vals

    @api.model
    def _create_payment_entry(self, amount):
        """ Create a journal entry corresponding to a payment, if the payment references invoice(s) they are reconciled.
            Return the journal entry.
        """
        aml_obj = self.env['account.move.line'].with_context(check_move_validity=False)
        debit, credit, amount_currency, currency_id = aml_obj.with_context(
            date=self.payment_date)._compute_amount_fields(amount, self.currency_id, self.company_id.currency_id)

        move = self.env['account.move'].create(self._get_move_vals())

        # Write line corresponding to invoice payment
        counterpart_aml_dict = self._get_shared_move_line_vals(debit, credit, amount_currency, move.id, False)
        counterpart_aml_dict.update(self._get_counterpart_move_line_vals(self.invoice_ids))
        counterpart_aml_dict.update({'currency_id': currency_id})
        counterpart_aml_dict = self.generate_account_analytic_lines_move(counterpart_aml_dict)
        counterpart_aml = aml_obj.create(counterpart_aml_dict)

        # Reconcile with the invoices
        if self.payment_difference_handling == 'reconcile' and self.payment_difference:
            writeoff_line = self._get_shared_move_line_vals(0, 0, 0, move.id, False)
            debit_wo, credit_wo, amount_currency_wo, currency_id = aml_obj.with_context(
                date=self.payment_date)._compute_amount_fields(self.payment_difference, self.currency_id,
                                                               self.company_id.currency_id)
            writeoff_line['name'] = self.writeoff_label
            writeoff_line['account_id'] = self.writeoff_account_id.id
            writeoff_line['debit'] = debit_wo
            writeoff_line['credit'] = credit_wo
            writeoff_line['amount_currency'] = amount_currency_wo
            writeoff_line['currency_id'] = currency_id
            writeoff_line = aml_obj.create(writeoff_line)
            if counterpart_aml['debit'] or (writeoff_line['credit'] and not counterpart_aml['credit']):
                counterpart_aml['debit'] += credit_wo - debit_wo
            if counterpart_aml['credit'] or (writeoff_line['debit'] and not counterpart_aml['debit']):
                counterpart_aml['credit'] += debit_wo - credit_wo
            counterpart_aml['amount_currency'] -= amount_currency_wo

        # Write counterpart lines
        if not self.currency_id.is_zero(self.amount):
            if not self.currency_id != self.company_id.currency_id:
                amount_currency = 0
            liquidity_aml_dict = self._get_shared_move_line_vals(credit, debit, -amount_currency, move.id, False)
            liquidity_aml_dict.update(self._get_liquidity_move_line_vals(-amount))
            aml_obj.create(liquidity_aml_dict)

        # validate the payment
        if not self.journal_id.post_at_bank_rec:
            move.post()

        # reconcile the invoice receivable/payable line(s) with the payment
        if self.invoice_ids:
            self.invoice_ids.register_payment(counterpart_aml)

        return move

    def generate_account_analytic_lines_move(self, dict_actual):
        if not self.invoice_ids:
            return dict_actual

        invoice_ids = self.invoice_ids.filtered(lambda inv: not inv.default_ac_analytic_id)
        if not invoice_ids:
            return dict_actual

        move = self.env['account.move'].search([('id', '=', dict_actual['move_id'])])
        lines_account = []
        for invoice in invoice_ids:
            if invoice.invoice_line_ids:
                line_ids = invoice.invoice_line_ids.filtered(lambda l: l.account_analytic_id)
                if not line_ids:
                    return dict_actual

                for line in line_ids:
                    cant = line.quantity
                    imp = 0
                    if dict_actual['debit'] > 0:
                        imp = line.price_total * -1
                    else:
                        imp = line.price_total

                    dict_create = {
                        'name': dict_actual['name'],
                        'ref': move.ref if move else '',
                        'partner_id': dict_actual['partner_id'] if dict_actual.get('partner_id') else False,
                        'date': move.date,
                        'company_id': move.company_id.id,
                        'general_account_id': dict_actual['account_id'],
                        'unit_amount': cant,
                        'amount': imp,
                        'account_id': line.account_analytic_id.id,
                        'product_id': line.product_id.id,
                        'product_uom_id': line.uom_id.id
                    }
                    lines_account.append((0, 0, dict_create))
        if lines_account:
            dict_actual['analytic_line_ids'] = lines_account
        return dict_actual

    def _get_move_vals(self, journal=None):
        """ Return dict to create the payment move
        """
        journal = journal or self.journal_id
        default_account_analytic = ''
        if self.invoice_ids:
            invoice_ids = self.invoice_ids.filtered(lambda inv: inv.default_ac_analytic_id != False)
            if invoice_ids:
                default_account_analytic = invoice_ids[0].default_ac_analytic_id

        move_vals = {
            'date': self.payment_date,
            'ref': self.communication or '',
            'company_id': self.company_id.id,
            'journal_id': journal.id,
        }
        if default_account_analytic:
            move_vals['default_account_analytic'] = default_account_analytic.id
        name = False
        if self.move_name:
            names = self.move_name.split(self._get_move_name_transfer_separator())
            if self.payment_type == 'transfer':
                if journal == self.destination_journal_id and len(names) == 2:
                    name = names[1]
                elif journal == self.destination_journal_id and len(names) != 2:
                    # We are probably transforming a classical payment into a transfer
                    name = False
                else:
                    name = names[0]
            else:
                name = names[0]

        if name:
            move_vals['name'] = name
        return move_vals

    def fix_duplicate_payments(self):
        sql_payments = """
            SELECT p1.id p1id, p2.id p2id, p1.amount, p2.amount
            FROM account_payment p1
            JOIN account_payment p2 ON p1.amount = p2.amount AND p1.journal_id = p2.journal_id AND p1.payment_date = p2.payment_date
            WHERE p1.state != 'reconciled' AND p2.state = 'reconciled';
        """
        self.env.cr.execute(sql_payments)
        for match in self.env.cr.dictfetchall():
            p1 = self.env['account.payment'].browse(int(match['p1id']))
            p2 = self.env['account.payment'].browse(int(match['p2id']))
            move_payments_sql = """
                UPDATE account_payment
                SET partner_id = {partner}, partner_type = '{type}'
                WHERE id = {p2};
                UPDATE account_payment
                SET state = 'draft', sequence = 111, move_name = NULL
                WHERE id = {p1};
                UPDATE account_invoice_payment_rel
                SET payment_id = {p2}
                WHERE payment_id = {p1}; 
            """.format(
                p1=p1.id,
                p2=p2.id,
                partner=p1.partner_id.id,
                type=p1.partner_type
            )
            self.env.cr.execute(move_payments_sql)
        sql_delete = """
            DELETE
            FROM account_partial_reconcile
            WHERE credit_move_id IN (
              SELECT line.id
              FROM account_move_line line
                     JOIN account_payment pay ON line.payment_id = pay.id
              WHERE pay.sequence = 111
            )
               OR debit_move_id IN (
              SELECT line.id
              FROM account_move_line line
                     JOIN account_payment pay ON line.payment_id = pay.id
              WHERE pay.sequence = 111
            );
            DELETE
            FROM account_move
            WHERE id IN (
              SELECT DISTINCT line.move_id
              FROM account_move_line line
                     JOIN account_payment pay ON line.payment_id = pay.id
              WHERE pay.sequence = 111
            );
            DELETE
            FROM account_payment
            WHERE sequence = 111;
        """
        self.env.cr.execute(sql_delete)

    def danger_delete_payments(self):
        sql_payments = """
            SELECT string_agg(CAST(id AS VARCHAR), ',') ids, amount, date
            FROM account_move
            WHERE move_type IN ('liquidity')
            GROUP BY amount, date
            HAVING COUNT(id) > 1 AND COUNT(id) < 3;
        """
        self.env.cr.execute(sql_payments)
        for match in self.env.cr.dictfetchall():
            move_ids = str(match['ids']).split(',')
            move1 = self.env['account.move'].browse(int(move_ids[0]))
            move2 = self.env['account.move'].browse(int(move_ids[1]))
            if move1.state == 'posted' and move2.state == 'posted':
                continue
            if not move1.partner_id and not move2.partner_id and not move1.ref and not move2.ref:
                continue
            move1.write({
                'code_repeat': match['ids']
            })
            move2.write({
                'code_repeat': match['ids']
            })


class AccountPaymentAbstract(models.AbstractModel):
    _inherit = "account.abstract.payment"

    @api.multi
    @api.depends('payment_method_code')
    def _compute_show_partner_bank(self):
        """ Computes if the destination bank account must be displayed in the payment form view. By default, it
        won't be displayed but some modules might change that, depending on the payment type."""
        for payment in self:
            payment.show_partner_bank_account = False
