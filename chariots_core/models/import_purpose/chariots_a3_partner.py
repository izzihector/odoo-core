# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)


class ChariotsImportPartner(models.Model):

    _name = "chariots.import.partner"
    _description = "Chariots: Modelo transicional de Proveedores"

    number = fields.Char(string="Cuenta")
    name = fields.Char(string="Nombre")
    vat = fields.Char(string="NIF")
    is_iva_zero = fields.Boolean(string="Tiene IVA 0%?")
    is_iva_four = fields.Boolean(string="Tiene IVA 4%?")
    is_iva_ten = fields.Boolean(string="Tiene IVA 10%?")
    is_iva_twenty_one = fields.Boolean(string="Tiene IVA 21%?")
    retention = fields.Char(string="Retención")
    property_account_payable_id = fields.Many2one('account.account',string='Cuenta a pagar')
    supplier_id = fields.Many2one('res.partner',string='Proveedor asociado')
    fiscal_position_id = fields.Many2one('account.fiscal.position',string='Posición fiscal')
    partner_bank_id = fields.Many2one('res.partner.bank',string='Banco del proveedor')
    is_account_payable_import = fields.Boolean('Se ha creado correctamente la cuenta contable?')
    notes_partner = fields.Char(string='Notas')

    @api.model
    def migrate_account_supplier(self):
        a3_account_suppliers = self.env['chariots.import.partner'].search([])
        codes = []
        # Recogemos los objetos necesarios
        res_partner_obj = self.env['res.partner']
        res_partner_bank_obj = self.env['res.partner.bank']
        res_bank_obj = self.env['res.bank']
        acc_obj = self.env['account.account']
        fiscal_position_obj = self.env['account.fiscal.position']
        # logging.error(a3_account_suppliers)
        for a3_account in a3_account_suppliers:
            try:
                # Para comprobar si tiene un proveedor asociado
                if not a3_account.supplier_id:
                    
                    # Revisar que proveedores no tienen NIF
                    if a3_account.vat:
                        supplier = res_partner_obj.search([('supplier', '=', True),('vat', '=', a3_account.vat)])
                        a3_account.write({'supplier_id': supplier.id})
                if a3_account.retention and not a3_account.fiscal_position_id:
                    fiscal_position = fiscal_position_obj.search([('name', 'like', ('IRPF '+a3_account.retention))])
                    if fiscal_position:
                        a3_account.write({'fiscal_position_id': fiscal_position.id})
                    
                # Para comprobar que no tengan la misma cuenta (para ahorrar tiempo)
                if a3_account.property_account_payable_id.id == a3_account.supplier_id.property_account_payable_id.id:
                    continue
                
                # Para crear todo desde cero
                if not a3_account.partner_bank_id:
                    if not a3_account.supplier_id.comment:
                        continue
                    else:
                        a3_account.write({'notes_partner': a3_account.supplier_id.comment})
                        account_bank_partner = str(a3_account.supplier_id.comment)
                        logging.error(account_bank_partner)
                        account_bank_partner_list = account_bank_partner.split(' ')
                        # logging.error(account_bank_partner_list)
                        # logging.error(a3_account.supplier_id.name)
                        code_bank = account_bank_partner_list[1]
                        search_bank = res_bank_obj.search([('code', '=', code_bank)])
                        if not search_bank:
                            logging.error('NO SE HA ENCONTRADO NINGUN BANCO CON ESE CODIGO PARA EL PROVEEDOR: '+ a3_account.supplier_id.name)
                            continue
                        bank_id = search_bank
                        
                        search_res_partner_bank = res_partner_bank_obj.search([('acc_number', '=', account_bank_partner)])
                        
                        if search_res_partner_bank:
                            if not a3_account.partner_bank_id:
                                a3_account.write({'partner_bank_id': search_res_partner_bank.id})
                        else:
                            new_res_partner_bank = res_partner_bank_obj.create({
                                'bank_id': bank_id.id,
                                'partner_id': a3_account.supplier_id.id,
                                'acc_number': account_bank_partner
                            })
                            a3_account.write({'partner_bank_id': new_res_partner_bank.id})

                        search_account = acc_obj.search([('code','=', a3_account.number)])
                        code_number_account = str(a3_account.number)
                        code_number_account = code_number_account[0:3]
                        search_acc_group = self.env['account.group'].search([('code_prefix', '=', code_number_account)])
                        
                        if not search_account:
                            account_type_payable = self.env['account.account.type'].search([('type', '=', 'payable')])
                            if not account_type_payable:
                                continue
                            new_account = acc_obj.create({
                                'code': a3_account.number,
                                'user_type_id': account_type_payable.id,
                                'name': a3_account.name,
                                'company_id': self.env.user.company_id.id,
                                'reconcile': True
                            })
                            
                            if new_account:
                                if search_acc_group:
                                    acc_group = search_acc_group
                                    new_account.write({'group_id': acc_group.id})
                            
                            a3_account.write({'property_account_payable_id': new_account.id})
                            a3_account.supplier_id.write({'comment': ''})

                        else:
                            if search_account.id == a3_account.property_account_payable_id.id:
                                continue
                            else:
                                a3_account.write({'property_account_payable_id': search_account.id})
                
                if a3_account.property_account_payable_id:
                    a3_account.write({'is_account_payable_import': True})
            
            except Exception as e:
                # Que hacemos aqui?
                logging.error('ERROR AL MIGRAR EL PROVEEDOR')
                logging.error('EL PROVEEDOR TIENE NOMBRE: '+ a3_account.name)
                logging.error(e)
