# -*- coding: utf-8 -*-


from odoo import api, fields, models, _
import logging
from odoo.exceptions import AccessError, UserError, RedirectWarning, ValidationError, Warning


class AccountAccount(models.Model):
    _inherit = 'account.account'

    code_number = fields.Integer(string="Código Entero", store=True, compute="_compute_code_number")

    @api.depends('code')
    @api.multi
    def _compute_code_number(self):
        for account in self:
            try:
                code = account.code
                code = code.replace('-','')
                account.code_number = int(code)
            except:
                pass

    @api.multi
    def _check_code_format(self, code=False):
        for account in self:
            if not code:
                code = account.code
            # Si no tiene la cantidad de caracteres necesarios
            if len(code) > 9:
                raise UserError(_("El código no contiene los 8 digitos y el guión"))
            else:
                if len(code) <= 9:
                    long_fault = 9 - len(code)
                    if long_fault !=0: 
                        for i in range(0, long_fault):
                            code += '0'
                        
                        if len(code) == 9:
                            new_code = code[0:4] + '-' + code[4] + code[5] + code[6] + code[7]
                            code = new_code  
                    else:
                        new_code = code[0:4] + '-' + code[5] + code[6] + code[7] + code[8]
                        code = new_code  

            # Primeros 4 digitos
            first_numbers = code[0:4]

            try:
                first_numbers_int = int(first_numbers)
            except Exception as e:
                raise UserError(_("Has puesto algo mal en los primeros 4 digitos"))

            # Signo del guión
            guion = code[4:5]
            if not guion == '-':
                raise UserError(_("No has puesto un guión entre medias de los 4 digitos"))

            # Últimos 4 digitos
            last_numbers = code[5:len(code)]
            try:
                last_numbers_int = int(last_numbers)
            except Exception as e:
                raise UserError(_("Has puesto algo mal en los ultimos 4 digitos"))

            if first_numbers_int >= 0 and first_numbers_int <= 9999 and guion == '-' and last_numbers_int >= 0 and last_numbers_int <= 9999:
                return code
            else:
                raise UserError(_("El código de la cuenta contable no cumple con los requisitos revisa los digitos y si tiene guión"))                  
    
    @api.model
    def create(self, vals):
        account = super(AccountAccount, self).create(vals)
        account.code = account._check_code_format()
        return account

    @api.multi
    def write(self, vals):
        if 'code' in vals:
            vals['code'] = self._check_code_format(vals['code'])
        account = super(AccountAccount, self).write(vals)
        return account
    
    @api.model
    def duplicate_data(self, primary_company_id, secondary_company_id):
        obj_model = self.env[self._name]
        if primary_company_id and secondary_company_id:
            accounts = obj_model.sudo().search([('company_id', '=', primary_company_id.id)])
            if accounts:
                for account in accounts:
                    code = account._check_code_format(code=account.code)
                    search_account = obj_model.sudo().search([('code', '=', code), ('company_id', '=', secondary_company_id.id)])
                    if search_account: 
                        continue
                    
                    dicc = {
                        'company_id': secondary_company_id.id,
                        'code': code
                    }
                    new_account = account.copy(default=dicc)
