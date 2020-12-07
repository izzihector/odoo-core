# -*- coding: utf-8 -*-


from odoo import api, fields, models, _
import logging


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    acc_number_raw = fields.Char(string='Cta banc sin codigo', help='Aqui se pone la cuenta bancaria que aparecen en los ficheros txt')

    # TODO: Aplicar restricción para 4 dígitos, guión medio y 4 digitos. Migrar las cuentas a este formato.

    @api.model
    def duplicate_data(self, primary_company_id, secondary_company_id):
        obj_model = self.env[self._name]
        account_obj = self.env['account.account']
        res_partner_bank_obj = self.env['res.partner.bank']
        ir_sequence_obj = self.env['ir.sequence']

        if primary_company_id and secondary_company_id:
            journals = obj_model.sudo().search([('company_id', '=', primary_company_id.id)])
            if journals:
                for journal in journals:
                    search_journal = obj_model.sudo().search([('code', '=', journal.code), ('company_id', '=', secondary_company_id.id)])
                    if search_journal: 
                        continue
                    search_sequence = ir_sequence_obj.sudo().search([('name', '=', journal.sequence_id.name), ('company_id', '=', secondary_company_id.id)])
                    search_res_partner_bank = res_partner_bank_obj.sudo().search([('acc_number', '=', journal.bank_account_id.acc_number),  ('company_id', '=', secondary_company_id.id)])
                    logging.error(search_res_partner_bank)
                    if not search_res_partner_bank and journal.bank_account_id:
                        new_bank_account_id = journal.bank_account_id.copy(default={
                            'partner_id': secondary_company_id.partner_id.id,
                            'company_id': secondary_company_id.id,
                            'acc_holder_name': secondary_company_id.name
                        })
                        search_res_partner_bank = new_bank_account_id
                    
                    code_debit = journal.default_debit_account_id._check_code_format()
                    code_credit = journal.default_credit_account_id._check_code_format()
                    search_debit_account_id = account_obj.sudo().search([('code', '=', code_debit), ('company_id', '=', secondary_company_id.id)])
                    search_credit_account_id = account_obj.sudo().search([('code', '=', code_credit), ('company_id', '=', secondary_company_id.id)])

                    dicc = {
                        'company_id': secondary_company_id.id,
                        'bank_account_id': search_res_partner_bank.id,
                        'sequence_id': search_sequence.id,
                        
                    }
                    new_journal = journal.copy(default=dicc)
                    new_journal.write({'name': journal.name})
                    if search_debit_account_id:
                        new_journal.write({'default_debit_account_id': search_debit_account_id.id})
                    if search_credit_account_id:
                        new_journal.write({'default_credit_account_id': search_credit_account_id.id})