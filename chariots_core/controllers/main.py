# -*- coding: utf-8 -*-
import json
import datetime
from odoo import http
from odoo.http import request, content_disposition
from odoo.tools.misc import xlwt
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT
import logging

class DownloadExcel(http.Controller):

    @http.route(['/chariots/download_excel_invoice'], type='http', auth='user')
    def download_excel_account_invoice(self, date_from, date_to, customer_ids, supplier_ids, type, *args, **kwargs):
        workbook = xlwt.Workbook(style_compression=2)
        worksheet = workbook.add_sheet('FACTURAS')
        worksheet_refunds = workbook.add_sheet('FACTURAS RECTIFICATIVAS')
        worksheet_intracomunitary = workbook.add_sheet('INTRACOMUNITARIAS')
        worksheet_inversion = workbook.add_sheet('INVERSION')

        row = 6
        col = 0
        acc_inv_obj = request.env['account.invoice']
        columns = []
        field_names = []
        customers = json.loads(customer_ids)
        suppliers = json.loads(supplier_ids)
        query = """"""
        records = {'invoices': {'total_invoices': 0, 'total_taxes': {},'invoices':{}},'refunds':{'total_invoices': 0, 'total_taxes': {},'refunds':{}},'intracomunitary':{'total_invoices': 0, 'total_taxes': {},'intracomunitary':{}},'inversion':{'total_invoices': 0, 'total_taxes': {},'inversion':{}}}
        fiscal_position_intracomunitary = request.env['ir.property'].sudo().search([('name', '=', 'fiscal_position_id_intracomunitary')])
        fiscal_position_intracomunitary = fiscal_position_intracomunitary.value_reference.split(',')
        fiscal_position_intracomunitary = int(fiscal_position_intracomunitary[1])
        fiscal_position_intracomunitary = request.env['account.fiscal.position'].sudo().search([('id', '=', fiscal_position_intracomunitary)])
        fiscal_position_inversion = request.env['ir.property'].sudo().search([('name', '=', 'fiscal_position_id_inversion')])
        fiscal_position_inversion = fiscal_position_inversion.value_reference.split(',')
        fiscal_position_inversion = int(fiscal_position_inversion[1])
        fiscal_position_inversion = request.env['account.fiscal.position'].sudo().search([('id', '=', fiscal_position_inversion)])
        # Informes de clientes
        if type == 'customer':
            columns = ['Nº Orden','Núm Factura','Fecha Factura','Concepto','NIF','Expedidor','Base imponible','%IVA','Cuota']
            field_names = ['num_order','number_invoice','date_invoice','concept','vat','name_client','amount_untaxed','percent_tax','amount_tax']
            col_sizes = [5000,5000,8000,8000,5000,5000,8000,9000,3000,9000]
            if customer_ids != '[]':
                customers = json.loads(customer_ids)
                customs = []
                for customer in customers:
                    search_customer = request.env['res.partner'].browse(customer)
                    customs.append(search_customer.id)
            else:
                customs = [customer.id for customer in request.env['res.partner'].sudo().search([
                    ('customer', '=', True),
                    ('parent_id', '=', False)
                ])]
            customs = str(customs)
            customs = customs.replace('[','(')
            customs = customs.replace(']',')')
            query = """
                SELECT id as invoice_id FROM account_invoice
                WHERE partner_id IN {} and date_invoice BETWEEN '{}' and '{}' and type in ('out_refund','out_invoice') and state not in ('draft','cancel')
                ORDER BY partner_id, date_invoice ASC
            """.format(customs, date_from, date_to)
            acc_inv_obj._cr.execute(query)
            results = acc_inv_obj._cr.fetchall()
            
            for invoice_id in results:
                invoice = acc_inv_obj.sudo().browse(invoice_id)
                window = ''
                if invoice.partner_id.property_account_position_id:
                    if invoice.partner_id.property_account_position_id.id == fiscal_position_intracomunitary.id:
                        window = 'intracomunitary' 
                    elif invoice.partner_id.property_account_position_id.id == fiscal_position_inversion.id:
                        window = 'inversion' 
                else:
                    if invoice.type == 'out_invoice':
                       window = 'invoices' 
                    else:
                       window = 'refunds'
                number = invoice.number
                date_invoice_str = datetime.datetime.strptime(str(invoice.date_invoice), DEFAULT_SERVER_DATE_FORMAT).strftime('%d/%m/%Y')
                nif = invoice.partner_id.vat
                client_name = invoice.partner_id.name
                amount_untaxed_invoice_signed = invoice.amount_untaxed_invoice_signed
                reference = str(number).split('/')[-1]
                taxes = {}
                factor = 1
                if invoice.type == 'out_refund':
                    factor = -1
                if invoice.tax_line_ids:
                    tax_line_ids = invoice.tax_line_ids
                    for tax_line in tax_line_ids:
                        if int(tax_line.tax_id.amount) not in taxes:
                            taxes[tax_line.tax_id.amount] = {
                                'tax_name': tax_line.tax_id.name,
                                'tax_amount': int(tax_line.tax_id.amount),
                                'tax_amount_invoice': tax_line.amount * factor,
                                'tax_base': tax_line.base * factor
                            }
                        else:
                            taxes[int(tax_line.tax_id.amount)]['tax_amount_invoice'] += tax_line.amount
                            taxes[int(tax_line.tax_id.amount)]['tax_base'] += tax_line.base      
    

                        if int(tax_line.tax_id.amount) not in records[window]['total_taxes']:
                            records[window]['total_taxes'][int(tax_line.tax_id.amount)] = {
                                'tax_name': tax_line.tax_id.name,
                                'tax_amount': int(tax_line.tax_id.amount),
                                'tax_amount_invoice': tax_line.amount * factor,
                                'tax_base': tax_line.base * factor
                            }
                        else:
                            records[window]['total_taxes'][int(tax_line.tax_id.amount)]['tax_amount_invoice'] += tax_line.amount * factor
                            records[window]['total_taxes'][int(tax_line.tax_id.amount)]['tax_base'] += tax_line.base  * factor    
    
                values = {
                    'client_name': client_name,
                    'amount_untaxed': amount_untaxed_invoice_signed,
                    'date_invoice': date_invoice_str,
                    'number': number,
                    'reference': reference,
                    'vat': nif,
                    'taxes': taxes,
                    'sii_description': invoice.sii_description
                }

                records[window]['total_invoices'] += amount_untaxed_invoice_signed
                records[window][window][invoice.id] = values
        elif type == 'supplier':
            columns = ['Nº Orden','Núm Factura','Fecha Factura','Concepto','NIF','Expedidor','Base imponible','%IVA','Cuota']
            field_names = ['num_order','number_invoice','date_invoice','concept','vat','name_client','amount_untaxed','percent_tax','amount_tax']
            col_sizes = [5000,5000,8000,8000,5000,5000,8000,9000,3000,9000]
            suppliers = json.loads(supplier_ids)
            supp = []

            if supplier_ids != '[]':
                for supplier in suppliers:
                    search_supplier = request.env['res.partner'].browse(supplier)
                    supp.append(search_supplier.id)
            else:
                supp = [supplier.id for supplier in request.env['res.partner'].sudo().search([
                    ('supplier', '=', True),
                    ('parent_id', '=', False)
                ])]

            supp = str(supp)
            supp = supp.replace('[','(')
            supp = supp.replace(']',')')

            query = """
                SELECT id as invoice_id FROM account_invoice
                WHERE partner_id IN {} and date_invoice BETWEEN '{}' and '{}' and type in ('in_invoice','in_refund') and state not in ('draft','cancel')
                ORDER BY partner_id, date_invoice ASC
            """.format(supp, date_from, date_to)
            acc_inv_obj._cr.execute(query)
            results = acc_inv_obj._cr.fetchall()

            for invoice_id in results:
                invoice = acc_inv_obj.sudo().browse(invoice_id)
                window = ''
                if invoice.partner_id.property_account_position_id:
                    if invoice.partner_id.property_account_position_id.id == fiscal_position_intracomunitary.id:
                        window = 'intracomunitary' 
                    elif invoice.partner_id.property_account_position_id.id == fiscal_position_inversion.id:
                        window = 'inversion' 
                else:
                    if invoice.type == 'in_invoice':
                       window = 'invoices' 
                    else:
                       window = 'refunds'
                
                number = invoice.number
                reference = invoice.reference
                date_invoice_str =  datetime.datetime.strptime(str(invoice.date_invoice), DEFAULT_SERVER_DATE_FORMAT).strftime('%d/%m/%Y')
                nif = invoice.partner_id.vat
                client_name = invoice.partner_id.name
                amount_untaxed_invoice_signed = invoice.amount_untaxed_invoice_signed
                factor = 1
                if invoice.type == 'in_refund':
                    factor = -1
                taxes = {}
                if invoice.tax_line_ids:
                    tax_line_ids = invoice.tax_line_ids
                    for tax_line in tax_line_ids:
                        if int(tax_line.tax_id.amount) not in taxes:
                            taxes[tax_line.tax_id.amount] = {
                                'tax_name': tax_line.tax_id.name,
                                'tax_amount': int(tax_line.tax_id.amount),
                                'tax_amount_invoice': tax_line.amount * factor,
                                'tax_base': tax_line.base * factor
                            }
                        else:
                            taxes[int(tax_line.tax_id.amount)]['tax_amount_invoice'] += tax_line.amount * factor
                            taxes[int(tax_line.tax_id.amount)]['tax_base'] += tax_line.base * factor     
    

                        if int(tax_line.tax_id.amount) not in records[window]['total_taxes']:
                            records[window]['total_taxes'][int(tax_line.tax_id.amount)] = {
                                'tax_name': tax_line.tax_id.name,
                                'tax_amount': int(tax_line.tax_id.amount),
                                'tax_amount_invoice': tax_line.amount * factor,
                                'tax_base': tax_line.base * factor
                            }
                        else:
                            records[window]['total_taxes'][int(tax_line.tax_id.amount)]['tax_amount_invoice'] += tax_line.amount * factor
                            records[window]['total_taxes'][int(tax_line.tax_id.amount)]['tax_base'] += tax_line.base * factor     

                values = {
                    'client_name': client_name,
                    'amount_untaxed': amount_untaxed_invoice_signed,
                    'date_invoice': date_invoice_str,
                    'number': number,
                    'reference': reference,
                    'vat': nif,
                    'taxes': taxes,
                    'sii_description': invoice.sii_description
                }

                records[window]['total_invoices'] += amount_untaxed_invoice_signed
                records[window][window][invoice.id] = values
        # Informes de proveedores y clientes a la vez si no se ha metido ni clientes ni proveedores
        else:
            columns = ['Nº Orden','Núm Factura','Fecha Factura','Concepto','NIF','Expedidor','Base imponible','%IVA','Cuota']
            field_names = ['num_order','number_invoice','date_invoice','concept','vat','name_client','amount_untaxed','percent_tax','amount_tax']
            col_sizes = [5000,8000,8000,5000,5000,8000,9000,3000,9000]
            suppliers = request.env['res.partner'].search([('type', '!=', 'sale_point'),('supplier', '=', True), ('parent_id', '=', False)])
            supp = []

            customers = request.env['res.partner'].search([('type', '!=', 'sale_point'),('customer', '=', True), ('parent_id', '=', False)])
            customs = []

            supp = str(suppliers.ids)
            supp = supp.replace('[','(')
            supp = supp.replace(']',')')

            customs = str(customers.ids)
            customs = customs.replace('[','(')
            customs = customs.replace(']',')')


            # Facturas de proveedor
            query = """
                SELECT id as invoice_id FROM account_invoice
                WHERE partner_id IN {} and date_invoice BETWEEN '{}' and '{}' and type in ('in_invoice','in_refund') and state not in ('draft','cancel')
                ORDER BY partner_id, date_invoice ASC
            """.format(supp, date_from, date_to)
            acc_inv_obj._cr.execute(query)
            results = acc_inv_obj._cr.fetchall()

            for invoice_id in results:
                invoice = acc_inv_obj.sudo().browse(invoice_id)
                window = ''
                if invoice.partner_id.property_account_position_id:
                    if invoice.partner_id.property_account_position_id.id == fiscal_position_intracomunitary.id:
                        window = 'intracomunitary' 
                    elif invoice.partner_id.property_account_position_id.id == fiscal_position_inversion.id:
                        window = 'inversion' 
                else:
                    if invoice.type == 'in_invoice':
                       window = 'invoices' 
                    else:
                       window = 'refunds'
                
                number = invoice.number
                reference = invoice.reference
                date_invoice_str =  datetime.datetime.strptime(str(invoice.date_invoice), DEFAULT_SERVER_DATE_FORMAT).strftime('%d/%m/%Y')
                nif = invoice.partner_id.vat
                client_name = invoice.partner_id.name
                amount_untaxed_invoice_signed = invoice.amount_untaxed_invoice_signed
                factor = 1
                if invoice.type == 'in_refund':
                    factor = -1
                taxes = {}
                if invoice.tax_line_ids:
                    tax_line_ids = invoice.tax_line_ids
                    for tax_line in tax_line_ids:
                        if int(tax_line.tax_id.amount) not in taxes:
                            taxes[tax_line.tax_id.amount] = {
                                'tax_name': tax_line.tax_id.name,
                                'tax_amount': int(tax_line.tax_id.amount),
                                'tax_amount_invoice': tax_line.amount * factor,
                                'tax_base': tax_line.base * factor
                            }
                        else:
                            taxes[int(tax_line.tax_id.amount)]['tax_amount_invoice'] += tax_line.amount * factor
                            taxes[int(tax_line.tax_id.amount)]['tax_base'] += tax_line.base * factor     
    

                        if int(tax_line.tax_id.amount) not in records[window]['total_taxes']:
                            records[window]['total_taxes'][int(tax_line.tax_id.amount)] = {
                                'tax_name': tax_line.tax_id.name,
                                'tax_amount': int(tax_line.tax_id.amount),
                                'tax_amount_invoice': tax_line.amount * factor,
                                'tax_base': tax_line.base * factor
                            }
                        else:
                            records[window]['total_taxes'][int(tax_line.tax_id.amount)]['tax_amount_invoice'] += tax_line.amount * factor
                            records[window]['total_taxes'][int(tax_line.tax_id.amount)]['tax_base'] += tax_line.base * factor     

                values = {
                    'client_name': client_name,
                    'amount_untaxed': amount_untaxed_invoice_signed,
                    'date_invoice': date_invoice_str,
                    'number': number,
                    'reference': reference,
                    'vat': nif,
                    'taxes': taxes,
                    'sii_description': invoice.sii_description
                }

                records[window]['total_invoices'] += amount_untaxed_invoice_signed
                records[window][window][invoice.id] = values
            # Facturas de cliente
            query = """
                SELECT id as invoice_id FROM account_invoice
                WHERE partner_id IN {} and date_invoice BETWEEN '{}' and '{}' and type in ('out_refund','out_invoice') and state not in ('draft','cancel')
                ORDER BY partner_id, date_invoice ASC
            """.format(customs, date_from, date_to)
            acc_inv_obj._cr.execute(query)
            results = acc_inv_obj._cr.fetchall()
            for invoice_id in results:
                invoice = acc_inv_obj.sudo().browse(invoice_id)
                window = ''
                if invoice.partner_id.property_account_position_id:
                    if invoice.partner_id.property_account_position_id.id == fiscal_position_intracomunitary.id:
                        window = 'intracomunitary' 
                    elif invoice.partner_id.property_account_position_id.id == fiscal_position_inversion.id:
                        window = 'inversion' 
                else:
                    if invoice.type == 'out_invoice':
                       window = 'invoices' 
                    else:
                       window = 'refunds'
                number = invoice.number
                date_invoice_str = datetime.datetime.strptime(str(invoice.date_invoice), DEFAULT_SERVER_DATE_FORMAT).strftime('%d/%m/%Y')
                nif = invoice.partner_id.vat
                client_name = invoice.partner_id.name
                amount_untaxed_invoice_signed = invoice.amount_untaxed_invoice_signed
                reference = str(number).split('/')[-1]
                taxes = {}
                factor = 1
                if invoice.type == 'out_refund':
                    factor = -1
                if invoice.tax_line_ids:
                    tax_line_ids = invoice.tax_line_ids
                    for tax_line in tax_line_ids:
                        if int(tax_line.tax_id.amount) not in taxes:
                            taxes[tax_line.tax_id.amount] = {
                                'tax_name': tax_line.tax_id.name,
                                'tax_amount': int(tax_line.tax_id.amount),
                                'tax_amount_invoice': tax_line.amount * factor,
                                'tax_base': tax_line.base * factor
                            }
                        else:
                            taxes[int(tax_line.tax_id.amount)]['tax_amount_invoice'] += tax_line.amount
                            taxes[int(tax_line.tax_id.amount)]['tax_base'] += tax_line.base      
    

                        if int(tax_line.tax_id.amount) not in records[window]['total_taxes']:
                            records[window]['total_taxes'][int(tax_line.tax_id.amount)] = {
                                'tax_name': tax_line.tax_id.name,
                                'tax_amount': int(tax_line.tax_id.amount),
                                'tax_amount_invoice': tax_line.amount * factor,
                                'tax_base': tax_line.base * factor
                            }
                        else:
                            records[window]['total_taxes'][int(tax_line.tax_id.amount)]['tax_amount_invoice'] += tax_line.amount * factor
                            records[window]['total_taxes'][int(tax_line.tax_id.amount)]['tax_base'] += tax_line.base  * factor    
    
                values = {
                    'client_name': client_name,
                    'amount_untaxed': amount_untaxed_invoice_signed,
                    'date_invoice': date_invoice_str,
                    'number': number,
                    'reference': reference,
                    'vat': nif,
                    'taxes': taxes,
                    'sii_description': invoice.sii_description
                }
                records[window]['total_invoices'] += amount_untaxed_invoice_signed
                records[window][window][invoice.id] = values

        for record in columns:
            worksheet.write(row, col, record, xlwt.easyxf('align: horiz center;'))
            worksheet.col(col).width = col_sizes[col]
            worksheet_intracomunitary.write(row, col, record, xlwt.easyxf('align: horiz center;'))
            worksheet_intracomunitary.col(col).width = col_sizes[col]
            worksheet_refunds.write(row, col, record, xlwt.easyxf('align: horiz center;'))
            worksheet_refunds.col(col).width = col_sizes[col]
            worksheet_inversion.write(row, col, record, xlwt.easyxf('align: horiz center;'))
            worksheet_inversion.col(col).width = col_sizes[col]
            col += 1
        
        row += 1

        col_pos = {}
        col = 0
        for record in field_names:
            col_pos[record] = col
            col += 1
        invoices = records['invoices']['invoices']
        total_taxes = records['invoices']['total_taxes']
        total_invoices = records['invoices']['total_invoices']
        date_now = datetime.datetime.strptime(str(datetime.datetime.now().date()), DEFAULT_SERVER_DATE_FORMAT).strftime('%d/%m/%Y')
        date_to = datetime.datetime.strptime(date_to, DEFAULT_SERVER_DATE_FORMAT).strftime('%d/%m/%Y')
        date_from = datetime.datetime.strptime(date_from, DEFAULT_SERVER_DATE_FORMAT).strftime('%d/%m/%Y')

        worksheet.write(2, 0, 'Empresa: ' + request.env.user.company_id.name, xlwt.easyxf('font: bold on;'))
        worksheet.write(3, 0, 'Período: '+ date_from+' a '+date_to, xlwt.easyxf('font: bold on;'))
        worksheet.write(4, 0, 'Fecha: '+ date_now, xlwt.easyxf('font: bold on;'))
        worksheet_refunds.write(2, 0, 'Empresa: ' + request.env.user.company_id.name, xlwt.easyxf('font: bold on;'))
        worksheet_refunds.write(3, 0, 'Período: '+ date_from+' a '+date_to, xlwt.easyxf('font: bold on;'))
        worksheet_refunds.write(4, 0, 'Fecha: '+ date_now, xlwt.easyxf('font: bold on;'))
        worksheet_intracomunitary.write(2, 0, 'Empresa: ' + request.env.user.company_id.name, xlwt.easyxf('font: bold on;'))
        worksheet_intracomunitary.write(3, 0, 'Período: '+ date_from+' a '+date_to, xlwt.easyxf('font: bold on;'))
        worksheet_intracomunitary.write(4, 0, 'Fecha: '+ date_now, xlwt.easyxf('font: bold on;'))
        worksheet_inversion.write(2, 0, 'Empresa: ' + request.env.user.company_id.name, xlwt.easyxf('font: bold on;'))
        worksheet_inversion.write(3, 0, 'Período: '+ date_from+' a '+date_to, xlwt.easyxf('font: bold on;'))
        worksheet_inversion.write(4, 0, 'Fecha: '+ date_now, xlwt.easyxf('font: bold on;'))

        # Hoja Factura normal
        for invoice in invoices:
            taxes = invoices[invoice]['taxes']
            if taxes:
                amount_untaxed = False
                for tax in taxes:
                    if not amount_untaxed:
                        amount_untaxed = True

                    # Para saber si es del proveedor
                    if invoices[invoice]['reference']:
                        worksheet.write(row, 0, invoices[invoice]['reference'])
                    worksheet.write(row, 1, invoices[invoice]['number'])
                    worksheet.write(row, 2, invoices[invoice]['date_invoice'])
                    worksheet.write(row, 3, invoices[invoice]['sii_description'] if 'sii_description' in invoices[invoice] else "Sin Descripción")
                    worksheet.write(row, 4, invoices[invoice]['vat'])
                    worksheet.write(row, 5, invoices[invoice]['client_name'])
                    worksheet.write(row, 6, taxes[tax]['tax_base'])
                    worksheet.write(row, 7, taxes[tax]['tax_amount'])
                    worksheet.write(row, 8, taxes[tax]['tax_amount_invoice'])
                    row += 1
            else:
                # Para saber si tiene referencia
                if invoices[invoice]['reference']:
                    worksheet.write(row, 0, invoices[invoice]['reference'])

                worksheet.write(row, 1, invoices[invoice]['number'])
                worksheet.write(row, 2, invoices[invoice]['date_invoice'])
                worksheet.write(row, 3, invoices[invoice]['sii_description'])
                worksheet.write(row, 4, invoices[invoice]['vat'])
                worksheet.write(row, 5, invoices[invoice]['client_name'])
                worksheet.write(row, 6, invoices[invoice]['amount_untaxed'])
                row += 1
        row += 1
        worksheet.write(row, 5, 'Total Período', xlwt.easyxf('font: bold on;'))
        if total_taxes:
            for tax in total_taxes:
                worksheet.write(row, 6, total_taxes[tax]['tax_amount'], xlwt.easyxf('font: bold on;'))
                worksheet.write(row, 7, total_taxes[tax]['tax_base'], xlwt.easyxf('font: bold on;'))
                worksheet.write(row, 8, total_taxes[tax]['tax_amount_invoice'], xlwt.easyxf('font: bold on;'))
                row+=1
        row += 1

        worksheet.write(row, 6, 'Total Facturas', xlwt.easyxf('font: bold on;'))
        worksheet.write(row, 7, round(total_invoices, 2), xlwt.easyxf('font: bold on;'))
        row += 1
        
        # Hoja Factura rectificativa
        refunds = records['refunds']['refunds']
        total_taxes = records['refunds']['total_taxes']
        total_invoices = records['refunds']['total_invoices']
        row = 7

        for invoice in refunds:
            taxes = refunds[invoice]['taxes']
            if taxes:
                amount_untaxed = False
                for tax in taxes:
                    if not amount_untaxed:
                        amount_untaxed = True

                    # Para saber si es del proveedor
                    if refunds[invoice]['reference']:
                        worksheet_refunds.write(row, 0, refunds[invoice]['reference'])
                    worksheet_refunds.write(row, 1, refunds[invoice]['number'])
                    worksheet_refunds.write(row, 2, refunds[invoice]['date_invoice'])
                    worksheet_refunds.write(row, 3, refunds[invoice]['sii_description'] if 'sii_description' in refunds[invoice] else "Sin Descripción")
                    worksheet_refunds.write(row, 4, refunds[invoice]['vat'])
                    worksheet_refunds.write(row, 5, refunds[invoice]['client_name'])
                    worksheet_refunds.write(row, 6, taxes[tax]['tax_base'])
                    worksheet_refunds.write(row, 7, taxes[tax]['tax_amount'])
                    worksheet_refunds.write(row, 8, taxes[tax]['tax_amount_invoice'])
                    row += 1
            else:
                # Para saber si tiene referencia
                if refunds[invoice]['reference']:
                    worksheet_refunds.write(row, 0, refunds[invoice]['reference'])

                worksheet_refunds.write(row, 1, refunds[invoice]['number'])
                worksheet_refunds.write(row, 2, refunds[invoice]['date_invoice'])
                worksheet_refunds.write(row, 3, refunds[invoice]['sii_description'])
                worksheet_refunds.write(row, 4, refunds[invoice]['vat'])
                worksheet_refunds.write(row, 5, refunds[invoice]['client_name'])
                worksheet_refunds.write(row, 6, refunds[invoice]['amount_untaxed'])
                row += 1
        row += 1
        worksheet_refunds.write(row, 5, 'Total Período', xlwt.easyxf('font: bold on;'))
        if total_taxes:
            for tax in total_taxes:
                worksheet_refunds.write(row, 6, total_taxes[tax]['tax_amount'], xlwt.easyxf('font: bold on;'))
                worksheet_refunds.write(row, 7, total_taxes[tax]['tax_base'], xlwt.easyxf('font: bold on;'))
                worksheet_refunds.write(row, 8, total_taxes[tax]['tax_amount_invoice'], xlwt.easyxf('font: bold on;'))
                row+=1
        row += 1
        worksheet_refunds.write(row, 6, 'Total Facturas', xlwt.easyxf('font: bold on;'))
        worksheet_refunds.write(row, 7, round(total_invoices, 2), xlwt.easyxf('font: bold on;'))
        row += 1

        # Hoja intracomunitaria
        intracomunitary = records['intracomunitary']['intracomunitary']
        total_taxes = records['intracomunitary']['total_taxes']
        total_invoices = records['intracomunitary']['total_invoices']
        row = 7

        for invoice in intracomunitary:
            taxes = intracomunitary[invoice]['taxes']
            if taxes:
                amount_untaxed = False
                for tax in taxes:
                    if not amount_untaxed:
                        amount_untaxed = True

                    # Para saber si es del proveedor
                    if intracomunitary[invoice]['reference']:
                        worksheet_intracomunitary.write(row, 0, intracomunitary[invoice]['reference'])
                    worksheet_intracomunitary.write(row, 1, intracomunitary[invoice]['number'])
                    worksheet_intracomunitary.write(row, 2, intracomunitary[invoice]['date_invoice'])
                    worksheet_intracomunitary.write(row, 3, intracomunitary[invoice]['sii_description'] if 'sii_description' in intracomunitary[invoice] else "Sin Descripción")
                    worksheet_intracomunitary.write(row, 4, intracomunitary[invoice]['vat'])
                    worksheet_intracomunitary.write(row, 5, intracomunitary[invoice]['client_name'])
                    worksheet_intracomunitary.write(row, 6, taxes[tax]['tax_base'])
                    worksheet_intracomunitary.write(row, 7, taxes[tax]['tax_amount'])
                    worksheet_intracomunitary.write(row, 8, taxes[tax]['tax_amount_invoice'])
                    row += 1
            else:
                # Para saber si tiene referencia
                if intracomunitary[invoice]['reference']:
                    worksheet_intracomunitary.write(row, 0, intracomunitary[invoice]['reference'])

                worksheet_intracomunitary.write(row, 1, intracomunitary[invoice]['number'])
                worksheet_intracomunitary.write(row, 2, intracomunitary[invoice]['date_invoice'])
                worksheet_intracomunitary.write(row, 3, intracomunitary[invoice]['sii_description'])
                worksheet_intracomunitary.write(row, 4, intracomunitary[invoice]['vat'])
                worksheet_intracomunitary.write(row, 5, intracomunitary[invoice]['client_name'])
                worksheet_intracomunitary.write(row, 6, intracomunitary[invoice]['amount_untaxed'])
                row += 1
        row += 1
        worksheet_intracomunitary.write(row, 5, 'Total Período', xlwt.easyxf('font: bold on;'))
        if total_taxes:
            for tax in total_taxes:
                worksheet_intracomunitary.write(row, 6, total_taxes[tax]['tax_amount'], xlwt.easyxf('font: bold on;'))
                worksheet_intracomunitary.write(row, 7, total_taxes[tax]['tax_base'], xlwt.easyxf('font: bold on;'))
                worksheet_intracomunitary.write(row, 8, total_taxes[tax]['tax_amount_invoice'], xlwt.easyxf('font: bold on;'))
                row+=1
        row += 1
        worksheet_intracomunitary.write(row, 6, 'Total Facturas', xlwt.easyxf('font: bold on;'))
        worksheet_intracomunitary.write(row, 7, round(total_invoices, 2), xlwt.easyxf('font: bold on;'))
        row += 1

        # Hoja de inversion
        inversion = records['inversion']['inversion']
        total_taxes = records['inversion']['total_taxes']
        total_invoices = records['inversion']['total_invoices']
        row = 7

        for invoice in inversion:
            taxes = inversion[invoice]['taxes']
            if taxes:
                amount_untaxed = False
                for tax in taxes:
                    if not amount_untaxed:
                        amount_untaxed = True

                    # Para saber si es del proveedor
                    if inversion[invoice]['reference']:
                        worksheet_inversion.write(row, 0, inversion[invoice]['reference'])
                    worksheet_inversion.write(row, 1, inversion[invoice]['number'])
                    worksheet_inversion.write(row, 2, inversion[invoice]['date_invoice'])
                    worksheet_inversion.write(row, 3, inversion[invoice]['sii_description'] if 'sii_description' in inversion[invoice] else "Sin Descripción")
                    worksheet_inversion.write(row, 4, inversion[invoice]['vat'])
                    worksheet_inversion.write(row, 5, inversion[invoice]['client_name'])
                    worksheet_inversion.write(row, 6, taxes[tax]['tax_base'])
                    worksheet_inversion.write(row, 7, taxes[tax]['tax_amount'])
                    worksheet_inversion.write(row, 8, taxes[tax]['tax_amount_invoice'])
                    row += 1
            else:
                # Para saber si tiene referencia
                if intracomunitary[invoice]['reference']:
                    worksheet_inversion.write(row, 0, inversion[invoice]['reference'])

                worksheet_inversion.write(row, 1, inversion[invoice]['number'])
                worksheet_inversion.write(row, 2, inversion[invoice]['date_invoice'])
                worksheet_inversion.write(row, 3, inversion[invoice]['sii_description'])
                worksheet_inversion.write(row, 4, inversion[invoice]['vat'])
                worksheet_inversion.write(row, 5, inversion[invoice]['client_name'])
                worksheet_inversion.write(row, 6, inversion[invoice]['amount_untaxed'])
                row += 1
        row += 1
        worksheet_inversion.write(row, 5, 'Total Período', xlwt.easyxf('font: bold on;'))
        if total_taxes:
            for tax in total_taxes:
                worksheet_inversion.write(row, 6, total_taxes[tax]['tax_amount'], xlwt.easyxf('font: bold on;'))
                worksheet_inversion.write(row, 7, total_taxes[tax]['tax_base'], xlwt.easyxf('font: bold on;'))
                worksheet_inversion.write(row, 8, total_taxes[tax]['tax_amount_invoice'], xlwt.easyxf('font: bold on;'))
                row+=1
        row += 1
        worksheet_inversion.write(row, 6, 'Total Facturas', xlwt.easyxf('font: bold on;'))
        worksheet_inversion.write(row, 7, round(total_invoices, 2), xlwt.easyxf('font: bold on;'))
        row += 1

        response = request.make_response(
            None,
            headers=[('Content-Type', 'application/vnd.ms-excel'),
                     ('Content-Disposition', 'attachment; filename=Facturas.xls')],
        )
        workbook.save(response.stream)
        return response
