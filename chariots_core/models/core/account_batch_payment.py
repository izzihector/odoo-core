# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64
import logging
import time
import random
import os
from lxml import etree

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_repr, float_round, re


class AccountBatchPayment(models.Model):
    _inherit = 'account.batch.payment'

    is_file_sended = fields.Boolean(
        string="Archivo enviado al banco",
        default=False
    )
    batch_type = fields.Selection(
        selection_add=[
            ('transfer', 'Transferencia')
        ]
    )
    # Facturas
    invoice_ids = fields.Many2many(
        string="Facturas",
        compute="_compute_invoices",

    )
    invoices_count = fields.Integer(
        string="Nº Facturas",
        compute="_compute_invoices",

    )
    @api.multi
    @api.depends('payment_ids')
    def _compute_invoices(self):
        for bat in self:
            count = 0
            invoice_ids = []
            if bat.payment_ids:
                payment_ids = bat.payment_ids.filtered(lambda x: x.reconciled_invoice_ids != False)
                for pay in payment_ids:
                    for invoice in pay.reconciled_invoice_ids:
                        invoice_ids.append(invoice.id)
                count = len(invoice_ids)
            bat.invoice_ids = invoice_ids
            bat.invoices_count = count
    
    @api.multi
    def action_view_invoices(self):
        self.ensure_one()
        action = {
            'name': _('Facturas'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.invoice',
            'target': 'current',
        }
        invoice_ids = self.invoice_ids.ids
        if len(invoice_ids) == 1:
            action['res_id'] = invoice_ids[0]
            action['view_mode'] = 'form'
        else:
            action['view_mode'] = 'tree,form'
            action['domain'] = [('id', 'in', invoice_ids)]
        return action

    def send_to_bank(self):
        # Obtenemos parámetros de conexión de la DB
        domain = self.env['ir.config_parameter'].get_param('Ftp_Sabadell.domain')
        port = self.env['ir.config_parameter'].get_param('Ftp_Sabadell.port')
        username = self.env['ir.config_parameter'].get_param('Ftp_Sabadell.username')
        password = self.env['ir.config_parameter'].get_param('Ftp_Sabadell.password')
        local_path = self.env['ir.config_parameter'].get_param('Ftp_Sabadell.path')
        keyfile = "~/.ssh/id_rsa"
        data = base64.b64decode(self.export_file)
        filepath = "{}/{}".format(local_path, self.export_filename)
        remotepath = "/N34SEPA/{}".format(self.export_filename)
        f = open(filepath, mode="wb")
        f.write(data)
        f.close()
        # sftp [user]@host[:port][/dest_path] <<< $'put /local_path/file'
        cmd = "echo put {localpath} {remotepath} | sftp -i {keyfile} -P {port} {user}@{host}".format(
            keyfile=keyfile,
            port=str(22),
            user=username,
            host=domain,
            remotepath=remotepath,
            localpath=filepath
        )
        res = os.system(cmd)

        # Cambiamos la bandera a enviado
        self.is_file_sended = True

    def _create_iso20022_credit_transfer(self, Document, doc_payments):
        CstmrCdtTrfInitn = etree.SubElement(Document, "CstmrCdtTrfInitn")

        # Create the GrpHdr XML block
        GrpHdr = etree.SubElement(CstmrCdtTrfInitn, "GrpHdr")
        MsgId = etree.SubElement(GrpHdr, "MsgId")
        val_MsgId = "{}".format(self.name)
        val_MsgId = val_MsgId[-30:]
        MsgId.text = val_MsgId
        CreDtTm = etree.SubElement(GrpHdr, "CreDtTm")
        CreDtTm.text = time.strftime("%Y-%m-%dT%H:%M:%S")
        NbOfTxs = etree.SubElement(GrpHdr, "NbOfTxs")
        val_NbOfTxs = str(len(doc_payments))
        if len(val_NbOfTxs) > 15:
            raise ValidationError(_("Too many transactions for a single file."))
        if not self.journal_id.bank_account_id.bank_bic:
            raise UserError(_("There is no Bank Identifier Code recorded for bank account '%s' of journal '%s'") % (
                self.journal_id.bank_account_id.acc_number, self.journal_id.name))
        NbOfTxs.text = val_NbOfTxs
        CtrlSum = etree.SubElement(GrpHdr, "CtrlSum")
        CtrlSum.text = self._get_CtrlSum(doc_payments)
        GrpHdr.append(self._get_InitgPty())

        # Create one PmtInf XML block per execution date
        payments_date_wise = {}
        for payment in doc_payments:
            if payment.payment_date not in payments_date_wise:
                payments_date_wise[payment.payment_date] = []
            payments_date_wise[payment.payment_date].append(payment)
        count = 0
        for payment_date, payments_list in payments_date_wise.items():
            count += 1
            PmtInf = etree.SubElement(CstmrCdtTrfInitn, "PmtInf")
            PmtInfId = etree.SubElement(PmtInf, "PmtInfId")
            PmtInfId.text = (val_MsgId + str(self.journal_id.id) + str(count))[-30:]
            PmtMtd = etree.SubElement(PmtInf, "PmtMtd")
            PmtMtd.text = 'TRF'
            BtchBookg = etree.SubElement(PmtInf, "BtchBookg")
            BtchBookg.text = 'false'
            NbOfTxs = etree.SubElement(PmtInf, "NbOfTxs")
            NbOfTxs.text = str(len(payments_list))
            CtrlSum = etree.SubElement(PmtInf, "CtrlSum")
            CtrlSum.text = self._get_CtrlSum(payments_list)
            PmtInf.append(self._get_PmtTpInf())
            ReqdExctnDt = etree.SubElement(PmtInf, "ReqdExctnDt")
            ReqdExctnDt.text = fields.Date.to_string(payment_date)
            PmtInf.append(self._get_Dbtr())
            PmtInf.append(self._get_DbtrAcct())
            DbtrAgt = etree.SubElement(PmtInf, "DbtrAgt")
            FinInstnId = etree.SubElement(DbtrAgt, "FinInstnId")
            BIC = etree.SubElement(FinInstnId, "BIC")
            BIC.text = self.journal_id.bank_account_id.bank_bic.replace(' ', '')

            # One CdtTrfTxInf per transaction
            for payment in payments_list:
                PmtInf.append(self._get_CdtTrfTxInf(PmtInfId, payment))

        return etree.tostring(Document, pretty_print=True, xml_declaration=True, encoding='utf-8')

    def _get_CdtTrfTxInf(self, PmtInfId, payment):
        CdtTrfTxInf = etree.Element("CdtTrfTxInf")
        PmtId = etree.SubElement(CdtTrfTxInf, "PmtId")
        InstrId = etree.SubElement(PmtId, "InstrId")
        InstrId.text = self._sanitize_communication(payment.name)
        EndToEndId = etree.SubElement(PmtId, "EndToEndId")
        EndToEndId.text = "{}- {} -{}".format(
            payment.partner_id.ref if payment.partner_id.ref else payment.partner_id.display_name,
            str(payment.id),
            str(payment.communication)
        )[-30:]
        Amt = etree.SubElement(CdtTrfTxInf, "Amt")
        val_Ccy = payment.currency_id and payment.currency_id.name or payment.journal_id.company_id.currency_id.name
        val_InstdAmt = float_repr(float_round(payment.amount, 2), 2)
        max_digits = val_Ccy == 'EUR' and 11 or 15
        if len(re.sub('\.', '', val_InstdAmt)) > max_digits:
            raise ValidationError(_("The amount of the payment '%s' is too high. The maximum permitted is %s.") % (
            payment.name, str(9) * (max_digits - 3) + ".99"))
        InstdAmt = etree.SubElement(Amt, "InstdAmt", Ccy=val_Ccy)
        InstdAmt.text = val_InstdAmt
        CdtTrfTxInf.append(self._get_ChrgBr())
        CdtTrfTxInf.append(self._get_CdtrAgt(payment.partner_bank_account_id))
        Cdtr = etree.SubElement(CdtTrfTxInf, "Cdtr")
        Nm = etree.SubElement(Cdtr, "Nm")
        Nm.text = self._sanitize_communication(
            (payment.partner_bank_account_id.acc_holder_name or payment.partner_id.name)[:70])
        if payment.payment_type == 'transfer':
            CdtTrfTxInf.append(self._get_CdtrAcct(payment.destination_journal_id.bank_account_id))
        else:
            CdtTrfTxInf.append(self._get_CdtrAcct(payment.partner_bank_account_id))
        val_RmtInf = self._get_RmtInf(payment)
        if val_RmtInf is not False:
            CdtTrfTxInf.append(val_RmtInf)
        return CdtTrfTxInf
    
    def validate_batch(self): 
        if not self.payment_ids:
            raise UserError(_("No puedes validar este lote porque no tiene pagos."))
        
        if self.payment_ids:
            for payment in self.payment_ids:
                    payment_exists = self.env[self._name].search([])
                    if payment_exists:
                        payment_exists = payment_exists.filtered(lambda pay: pay.id != self.id and payment.id in pay.payment_ids.ids)
                        if len(payment_exists) > 0:
                            raise UserError(_("No puedes guardar el pago" + payment.name + " ya que existe en el pago" + payment_exists[0].name))
        
        res = super(AccountBatchPayment, self).validate_batch()
        if self.export_file:
            self.send_to_bank()
        return res 

    @api.model
    def create(self, vals):
        if 'payment_ids' not in vals:
            raise ValidationError(_("No puedes crear un lote sin pagos"))

        return super(AccountBatchPayment, self).create(vals)
    
 
    def unlink(self):
        for batch in self:
            if batch.state in ['sent', 'reconciled']:
                raise ValidationError(_('No puedes eliminar el lote '+ batch.name + ' porque no esta en borrador'))
        return super(AccountBatchPayment, self).unlink()
