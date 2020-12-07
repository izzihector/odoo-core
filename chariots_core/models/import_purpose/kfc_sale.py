# -*- coding: utf-8 -*-

import base64
import csv
import logging
from calendar import monthrange
from datetime import datetime, timedelta, date
from odoo.exceptions import UserError, ValidationError

import paramiko
from odoo import models, fields, api
from odoo.tools import float_is_zero

def custom_order(a, b):
    return 0


def clean_txt(txt):
    if not txt:
        return ""
    return str(txt).replace("'", '´')


class KfcSale(models.Model):
    _name = "chariots.import.kfc.sale"
    _description = "Chariots: Ventas de KFC"

    _sql_constraints = [
        ('external_id_unique', 'unique (external_id,date,store)', 'External ID ya existente.')
    ]

    name = fields.Char(
        string="Nombre",
        compute="_compute_name"
    )

    external_id = fields.Integer(
        string="ID KFC"
    )

    date = fields.Date(
        string="Fecha"
    )

    hour = fields.Char(
        string="Hora"
    )

    store = fields.Integer(
        string="Tienda ID"
    )

    canal = fields.Integer(
        string="Canal ID"
    )

    amount_total = fields.Float(
        string="Neto"
    )

    amount_subtotal = fields.Float(
        string="Bruto"
    )

    amount_tax = fields.Float(
        string="Impuestos"
    )

    trans_count = fields.Integer(
        string="Transa_Count"
    )

    n_lineas = fields.Integer(
        string="Nº de Líneas"
    )

    trans_status = fields.Char(
        string="Estado Transacción"
    )

    pago = fields.Integer(
        string="Método de Pago ID"
    )

    line_ids = fields.One2many(
        comodel_name="chariots.import.kfc.sale.line",
        string="Líneas de Ventas",
        inverse_name="sale_id"
    )

    store_id = fields.Many2one(
        comodel_name="chariots.import.kfc.store",
        string="Tienda"
    )

    channel_id = fields.Many2one(
        comodel_name="chariots.import.kfc.channel",
        string="Canal"
    )

    payment_method_id = fields.Many2one(
        comodel_name="chariots.import.kfc.paymethod",
        string="Método de pago"
    )

    range_id = fields.Many2one(
        comodel_name="chariots.import.kfc.timerange",
        string="Rango Horario"
    )

    is_imported = fields.Boolean(
        string="¿Ha sido importada?",
        default=False
    )
    calc_subtotal = fields.Float(
        string="Calculo del subtotal de venta",
        compute="_compute_sale_amounts",
        store=False
    )

    calc_total = fields.Float(
        string="Calculo del total de venta",
        compute="_compute_sale_amounts",
        store=False
    )

    calc_tax_ids = fields.One2many(
        string="Calculo de impuestos de venta",
        compute="_compute_sale_amounts",
        comodel_name="chariots.import.kfc.sale.tax",
        inverse_name="sale_id",

    )
    total_base = fields.Float(
        string="Total Base"
    )
    total_tax = fields.Float(
        string="Total Impuestos"
    )
    total_net = fields.Float(
        string="Total Neto"
    )
    total_discount = fields.Float(
        string="Total Descuento"
    )

    @api.multi
    @api.depends('line_ids')
    def _compute_sale_amounts(self):
        kfc_sale = self.env['chariots.import.kfc.sale']
        kfc_sale_tax = self.env['chariots.import.kfc.sale.tax']
        for sale in self:
            sale.calc_subtotal = float(0)
            sale.calc_total = float(0)
            sale.calc_tax_ids = False
            self.env.cr.execute("""
                DELETE FROM {table}
                WHERE sale_id = {sale_id};
            """.format(
                table=kfc_sale_tax._table,
                sale_id=sale.id
            ))
            query = kfc_sale._get_query_sale_total(
                dia=str(sale.date),
                where=" AND id = {}".format(sale.id),
                where_line=" AND sale_id = {}".format(sale.id)
            )
            self.env.cr.execute(query)
            results = self._cr.dictfetchall()
            for row in results:
                query = """
                    INSERT INTO chariots_import_kfc_sale_tax (
                        "sale_id", "payment_method_id", "channel_id", "store_id", "amount_subtotal", "amount_tax", "amount_total", "amount_total_fix", "tax_id", "date"
                    ) VALUES
                """
                query += """({}, {}, {}, {}, {}, {}, {}, {}, {}, '{}')""".format(
                    sale.id if sale else "NULL", sale.payment_method_id.id if sale.payment_method_id else "NULL", sale.channel_id.id if sale.channel_id else "NULL",
                    sale.store_id.id if sale.store_id else "NULL", row['amount_subtotal'], row['amount_tax'], row['amount_total'], 
                    row['amount_total_fix'], row['tax_id'] if row['tax_id'] else "NULL", sale.date
                )
                self.env.cr.execute(query)
                self.env.cr.commit()
                """sale.calc_tax_ids |= kfc_sale_tax.create({
                    'sale_id': sale.id,
                    'payment_method_id': sale.payment_method_id.id,
                    'channel_id': sale.channel_id.id,
                    'store_id': sale.store_id.id,
                    'amount_subtotal': row['amount_subtotal'],
                    'amount_tax': row['amount_tax'],
                    'amount_total': row['amount_total'],
                    'amount_total_fix': row['amount_total_fix'],
                    'tax_id': row['tax_id'],
                    'date': sale.date
                })"""

                sale.calc_subtotal += row['amount_total']
                sale.calc_total += row['amount_total_fix']

    def cron_compute_sale_amounts(self, date_init, date_end):
        #sales = self.env[self._name].search([('date', '>=', date_init), ('date', '<=', date_end)])
        self.env[self._name].query_kfc_sale_tax(date_init=date_init, date_end=date_end)

    @api.multi
    def _compute_name(self):
        for sale in self:
            sale.name = "Transacción {} en {}".format(sale.external_id, str(sale.date))

    @api.model
    def relate_models(self):
        """
        Este método ejecuta consultas SQL para relacionar las ventas con sus modelos de tablas de KFC
        tales como canal, tienda, venta...
        También genera el rango de tiempo en función de lo definido en la tabla de rangos
        :return:
        """
        query = """
            UPDATE chariots_import_kfc_sale AS sale
                SET store_id = x.id
                FROM chariots_import_kfc_store x
                WHERE x.external_id = sale.store AND sale.is_imported = false;
            UPDATE chariots_import_kfc_sale AS sale
                SET channel_id = x.id
                FROM chariots_import_kfc_channel x
                WHERE x.external_id = sale.canal AND sale.is_imported = false;
            UPDATE chariots_import_kfc_sale AS sale
                SET payment_method_id = x.id
                FROM chariots_import_kfc_paymethod x
                WHERE x.external_id = sale.pago AND sale.is_imported = false;
        """
        self.env.cr.execute(query)
        self.env.cr.commit()
        sales = self.env[self._name].search([
            ('range_id', '=', False),
            ('is_imported', '=', False)
        ])
        for sale in sales:
            data = {}
            hora_explode = str(sale.hour).split(':')
            minutes = int(hora_explode[1])
            hours = int(hora_explode[0])
            hora = (hours + (minutes / 60))
            search_range = self.env['chariots.import.kfc.timerange'].search([
                ('start_hour', '<=', float(hora)),
                ('end_hour', '>=', float(hora))
            ], limit=1)
            if search_range:
                data['range_id'] = search_range.id
            if data:
                sale.write(data)
                self.env.cr.commit()

    @api.model
    def caution_regenerate_payments(self, date_from="2020-01-01", date_to="2020-11-01"):
        """
        Con este método, ejecutado a través de cron, regeneramos los pagos para las facturas
        abiertas entre las fechas pasadas por parámetros
        :param date_from:
        :param date_to:
        :return:
        """
        # Buscamos todas las facturas
        inv_obj = self.env['account.invoice']
        invoices = inv_obj.search([
            ('journal_id.code', '=', 'INV'),
            ('real_sale_date', '>=', date_from),
            ('real_sale_date', '<=', date_to),
            ('state', '=', 'open')
        ])
        for inv in invoices:
            inv.generate_payment_by_method()
            self._cr.commit()

    @api.model
    def caution_regenerate_lines(self, date_from="2020-01-01", date_to="2020-11-01", delete_moves_before=False,
                                 force_state=False, filter_state=False, store_id_s=False):
        """
        Con este método, ejecutado a través de cron, regeneramos las facturas (solo líneas y asientos) de todas las
        facturas del diario de KFC (journal_id = 1)
        :param date_from:
        :param date_to:
        :param delete_moves_before:
        :param filter_state:
        :param force_state:
        :return:
        """
        if delete_moves_before:
            # Eliminamos todos los asientos del diario
            self._cr.execute("""
                UPDATE account_invoice SET move_id = NULL WHERE journal_id = 1;
                DELETE FROM account_move_line WHERE journal_id = 1;
                DELETE FROM account_move WHERE journal_id = 1;
            """)
            self._cr.commit()
        inv_obj = self.env['account.invoice']
        inv_line_obj = self.env['account.invoice.line']

        # Buscamos todas las facturas
        domain_invoices = [
            ('journal_id.code', '=', 'INV'),
            ('real_sale_date', '>=', date_from),
            ('real_sale_date', '<=', date_to),
        ]
        
        if filter_state:
            domain_invoices.append(('state', '=', filter_state))
        if store_id_s:
            domain_invoices.append(('partner_id', '=', store_id_s))
        invoices = inv_obj.search(domain_invoices)
        for inv in invoices:
            # Factura del 29 de julio que no tomamos en cuenta
            account_invoice_kfc_one = self.env['ir.property'].sudo().search([('name', '=', 'account_invoice_kfc_one')])
            account_invoice_kfc_one = account_invoice_kfc_one.value_reference.split(',')
            account_invoice_kfc_one = int(account_invoice_kfc_one[1])
            if inv.id == account_invoice_kfc_one:
                continue
            logging.info("Inicio de Factura {}".format(inv.id))
            # Por cada factura buscamos su tienda basada en la CA
            store_id = self.env['chariots.import.kfc.store'].search([
                ('analytic_account_id', '=', inv.default_ac_analytic_id.id)
            ], limit=1)
            # Almacenamos el estado de la factura
            if force_state:
                invoice_state = force_state
            else:
                invoice_state = str(inv.state)
            # Marcamos la factura como borrador y eliminamos todas sus líneas para regenerarlas.
            query_invoice = """
                UPDATE account_invoice
                SET state = 'draft'
                WHERE id = {invoice_id};
                DELETE
                FROM account_invoice_line
                WHERE invoice_id = {invoice_id};
            """.format(
                invoice_id=inv.id
            )
            self._cr.execute(query_invoice)
            # Hasta aquí forzamos a que las consultas se ejecuten de forma que estos datos ya estén guardados
            self._cr.commit()
            logging.info("Primer Commit {}".format(inv.id))
            # Obtenemos todas las ventas para la fecha de esta factura en la tienda indicada
            query_sales = self._get_query_sale_total_invoice(
                dia=str(inv.real_sale_date),
                where="AND store_id={}".format(store_id.id),
            )
            self._cr.execute(query_sales)
            results = self._cr.dictfetchall()
            line_list = []
            logging.info("Obtenemos datos de la query para ventas en {}".format(inv.id))
            amount_untaxed = 0.00
            update_tax_line_ids = {}
            update_invoice_lines = []
            for line in results:
                if line['amount_total_fix'] == 0:
                    continue
                channel_id = self.env['chariots.import.kfc.channel'].browse(int(line['channel_id']))
                # Por cada línea buscamos el producto basándonos en la CC del canal de venta
                product_id = self.env['product.product'].search([
                    ('property_account_income_id', '=', channel_id.account_id.id)
                ], limit=1)
                if not product_id:
                    # Si no hay producto entonces usamos un producto dummy o saltamos la línea
                    product_id = self.env['product.product'].search([
                        ('barcode', '=', 'producto-kfc-dummy')
                    ], limit=1)
                    if not product_id:
                        logging.info("El Producto con ID {} no existe".format(
                            channel_id.name
                        ))
                    continue
                # Creamos el dict para almacenar los datos de la línea de la factura
                data_line = {
                    'account_analytic_id': store_id.analytic_account_id.id if store_id.analytic_account_id else False,
                    'product_id': product_id.id,
                    'account_id': channel_id.account_id.id,
                    'quantity': 1.0,
                    'price_unit': line['amount_total_fix'] if inv.type == 'out_invoice' else line['amount_total_fix'] * -1,
                    'invoice_line_tax_ids': [(6, 0, [line['tax_id']])],
                    'name': "{}".format(
                        channel_id.name,
                    ),
                    'price_subtotal': line['amount_total'] if inv.type == 'out_invoice' else line['amount_total'] * -1,
                    'price_subtotal_signed': line['amount_total'] if inv.type == 'out_invoice' else line['amount_total'] * -1, 
                    'price_tax': line['amount_tax'] if inv.type == 'out_invoice' else line['amount_tax'] * -1,
                    'invoice_id': inv.id
                }
                new_inv_line = inv_line_obj.create(data_line)
                # Para actualizar lineas de impuesto
                if line['tax_id'] not in update_tax_line_ids:
                    update_tax_line_ids[line['tax_id']] = {
                        'amount': data_line['price_tax'],
                        'amount_total': data_line['price_tax'],
                        'amount_company': data_line['price_tax'],
                        'base_company': data_line['price_subtotal'],
                        'base': data_line['price_subtotal']
                    }
                else:
                    update_tax_line_ids[line['tax_id']]['amount'] += round(data_line['price_tax'], 2)
                    update_tax_line_ids[line['tax_id']]['amount_total'] += round(data_line['price_tax'], 2)
                    update_tax_line_ids[line['tax_id']]['amount_company'] += round(data_line['price_tax'], 2)
                    update_tax_line_ids[line['tax_id']]['base'] += round(data_line['price_subtotal'], 2)
                    update_tax_line_ids[line['tax_id']]['base_company'] += round(data_line['price_subtotal'], 2)

                # Forzamos por base de datos ya que nos sale 0 en el subtotal si no lo ponemos
                query_invoice_line = """
                    UPDATE account_invoice_line
                    SET price_subtotal = {price_subtotal}, price_total = {price_total}, price_unit = {price_unit}, price_subtotal_signed = {price_subtotal}
                    WHERE id = {inv_line_id};
                """.format(
                    inv_line_id=new_inv_line.id,
                    price_unit = data_line['price_unit'],
                    price_total = data_line['price_unit'],
                    price_subtotal = data_line['price_subtotal']
                )
                self._cr.execute(query_invoice_line)
                self._cr.commit()
                update_invoice_lines.append({
                    'id': new_inv_line.id,
                    'price_subtotal': data_line['price_subtotal'],
                    'price_total': data_line['price_unit'],
                    'price_unit': data_line['price_unit']
                })
                amount_untaxed += data_line['price_subtotal']
                #line_list.append((0, 0, data_line))
            logging.info("Añadimos todas las líneas {}".format(inv.id))
            # Añadidas las líneas a la factura y re-calculamos sus totales
            round_curr = inv.currency_id.round
            digits_rounding_precision = inv.currency_id.rounding
            amount_tax = sum(round_curr(line.amount_total) for line in inv.tax_line_ids)
            amount_total = amount_untaxed + amount_tax

            query_invoice_update = """
                UPDATE account_invoice
                SET 
                amount_total = {amount_total}, 
                amount_untaxed = {amount_untaxed}, 
                amount_tax = {amount_tax}, 
                amount_total_signed = {amount_total_signed},
                amount_untaxed_signed = {amount_untaxed_signed},
                amount_total_company_signed = {amount_total_company_signed},
                residual_company_signed = {residual_company_signed},
                residual_signed = {residual_signed},
                residual = {residual},
                reconciled = {reconciled}
                WHERE id = {inv_id};
            """.format(
                inv_id=inv.id,
                amount_total=amount_total,
                amount_untaxed=amount_untaxed,
                amount_tax=amount_tax,
                amount_total_signed=amount_total,
                amount_untaxed_signed=amount_untaxed,
                amount_total_company_signed=amount_total,
                residual_company_signed=amount_total,
                residual_signed=amount_total,
                residual=amount_total,
                reconciled= True if float_is_zero(amount_total, precision_rounding=digits_rounding_precision) else False
            )
            self._cr.execute(query_invoice_update)
            self._cr.commit()
           
            # Actualizamos lineas de impuesto
            if update_tax_line_ids and inv.tax_line_ids:
                for key, val in update_tax_line_ids.items():
                    query_invoice_tax_line_update = """
                        UPDATE account_invoice_tax
                        SET 
                        amount = {amount}, 
                        base = {base}
                        WHERE invoice_id = {inv_id} and tax_id = {tax_id};
                    """.format(
                        inv_id=inv.id,
                        tax_id=key,
                        amount=val['amount'],
                        base=val['base']
                    )
                    self._cr.execute(query_invoice_tax_line_update)
                    self._cr.commit()


            if inv.move_id:
                # Si la factura tiene asiento contable lo eliminamos para generar uno nuevo
                self._cr.execute("""
                    UPDATE account_invoice SET move_id = NULL WHERE move_id = {move_id};
                    DELETE FROM account_move_line WHERE move_id = {move_id};
                    DELETE FROM account_move WHERE id = {move_id}
                """.format(
                    move_id=inv.move_id.id,
                ))
            if invoice_state != 'draft':
                # Generamos el asiento contable si la factura no está en borrador
                inv.action_move_create()
                # Creamos el asiento de pago
                inv.generate_payment_by_method()
                
                # Forzamos a actualizar los valores si hemos generado de nuevo el asiento de la factura
                if inv.move_id:
                    if update_invoice_lines:
                        for val in update_invoice_lines:
                            query_invoice_line = """
                                UPDATE account_invoice_line
                                SET price_subtotal = {price_subtotal}, price_total = {price_total}, price_unit = {price_unit} 
                                WHERE id = {inv_line_id};
                            """.format(
                                inv_line_id=val['id'],
                                price_unit = val['price_unit'],
                                price_total = val['price_unit'],
                                price_subtotal = val['price_subtotal']
                            )
                            self._cr.execute(query_invoice_line)
                            self._cr.commit()
                        query_invoice_update = """
                            UPDATE account_invoice
                            SET 
                            amount_total = {amount_total}, 
                            amount_untaxed = {amount_untaxed}, 
                            amount_tax = {amount_tax}, 
                            amount_total_signed = {amount_total_signed},
                            amount_untaxed_signed = {amount_untaxed_signed},
                            amount_total_company_signed = {amount_total_company_signed},
                            residual_company_signed = {residual_company_signed},
                            residual_signed = {residual_signed},
                            residual = {residual},
                            reconciled = {reconciled}
                            WHERE id = {inv_id};
                        """.format(
                            inv_id=inv.id,
                            amount_total=amount_total,
                            amount_untaxed=amount_untaxed,
                            amount_tax=amount_tax,
                            amount_total_signed=amount_total,
                            amount_untaxed_signed=amount_untaxed,
                            amount_total_company_signed=amount_total,
                            residual_company_signed=amount_total,
                            residual_signed=amount_total,
                            residual=amount_total,
                            reconciled= True if float_is_zero(amount_total, precision_rounding=digits_rounding_precision) else False
                        )
                        self._cr.execute(query_invoice_update)
                        self._cr.commit()
                        # Actualizamos lineas de impuesto
                        if update_tax_line_ids and inv.tax_line_ids:
                            for key, val in update_tax_line_ids.items():
                                query_invoice_tax_line_update = """
                                    UPDATE account_invoice_tax
                                    SET 
                                    amount = {amount}, 
                                    base = {base}
                                    WHERE invoice_id = {inv_id} and tax_id = {tax_id};
                                """.format(
                                    inv_id=inv.id,
                                    tax_id=key,
                                    amount=val['amount'],
                                    base=val['base']
                                )
                                self._cr.execute(query_invoice_tax_line_update)
                                self._cr.commit()

            # Reestablecemos el estado de la factura
            query_invoice_update = """
                UPDATE account_invoice
                SET state = '{state}' 
                WHERE id = {inv_id};
            """.format(
                inv_id=inv.id,
                state=invoice_state
            )
            self._cr.execute(query_invoice_update)
            self._cr.commit()

    def _get_query_sale_total(self, dia, where='AND s.is_imported = false', where_line='AND sline.is_imported = false'):
        return """
            SELECT
                s.store_id,
                s.channel_id,
                total.tax_id,
                SUM(total.amount_subtotal) amount_subtotal,
                SUM(total.amount_tax) amount_tax,
                SUM(total.amount_total) amount_total,
                SUM(total.amount_total_fix) amount_total_fix,
                SUM(total.amount_total_discount) amount_total_discount
            FROM chariots_import_kfc_sale s 
            JOIN (
                SELECT
                    sale_id,
                    tax_id,
                    ROUND(SUM(sline.amount_subtotal)::numeric, 2) amount_subtotal,
                    ROUND(SUM(sline.amount_tax)::numeric, 2) amount_tax,
                    ROUND(SUM(sline.amount_total)::numeric, 2) amount_total,
                    ROUND(SUM(sline.amount_tax + sline.amount_total)::numeric, 2) amount_total_fix,
                    ROUND(SUM(sline.amount_subtotal - sline.amount_tax - sline.amount_total)::numeric, 2) amount_total_discount
                FROM chariots_import_kfc_sale_line sline
                WHERE sline.date >= '{dia}' AND sline.date <= '{dia}' {where_line} 
                GROUP BY sale_id, tax_id
            ) total ON total.sale_id = s.id 
            WHERE s.date >= '{dia}' AND s.date <= '{dia}' {where}
            GROUP BY s.store_id, s.channel_id, total.tax_id;  
        """.format(where=where, where_line=where_line, dia=dia)
    
    def query_update_kfc_sales(self):
        self._cr.execute("""
            UPDATE chariots_import_kfc_sale_line SET
            total_net = amount_tax + amount_total, discount = amount_subtotal - amount_tax - amount_total;

            UPDATE chariots_import_kfc_sale as s SET
            total_discount = sline.amount_total_discount, 
            total_base = sline.amount_subtotal, 
            total_tax = sline.amount_tax,
            total_net = sline.amount_total
            FROM (SELECT sale_id, 
                ROUND(SUM(amount_total)::numeric, 2) as amount_subtotal,
                ROUND(SUM(amount_tax)::numeric, 2) as amount_tax,
                ROUND(SUM(amount_tax + amount_total)::numeric, 2) as amount_total,
                ROUND(SUM(discount)::numeric, 2) as amount_total_discount
                FROM chariots_import_kfc_sale_line
                GROUP BY sale_id) sline
            WHERE s.id = sline.sale_id; 
        """)
        self._cr.commit()
    
    def query_kfc_sale_tax(self, date_init, date_end):
        self._cr.execute("""
            DELETE FROM chariots_import_kfc_sale_tax
            WHERE date >= '{date_init}' AND date <= '{date_end}';

            INSERT INTO chariots_import_kfc_sale_tax (
                "sale_id", "payment_method_id", "channel_id", "store_id", "amount_subtotal", "amount_tax", "amount_total", "amount_total_fix", "tax_id", "date"
            ) 
            SELECT
            s.id sale_id,
            s.payment_method_id payment_method_id,
            s.channel_id channel_id,
            s.store_id store_id,
            SUM(total.amount_subtotal) amount_subtotal,
            SUM(total.amount_tax) amount_tax,
            SUM(total.amount_total) amount_total,
            SUM(total.amount_total_fix) amount_total_fix,
            --SUM(total.amount_total_discount) amount_total_discount,
            total.tax_id tax_id,
            s.date
            FROM chariots_import_kfc_sale as s 
            JOIN (
                SELECT
                    sale_id,
                    tax_id,
                    ROUND(SUM(sline.amount_subtotal)::numeric, 2) amount_subtotal,
                    ROUND(SUM(sline.amount_tax)::numeric, 2) amount_tax,
                    ROUND(SUM(sline.amount_total)::numeric, 2) amount_total,
                    ROUND(SUM(sline.amount_tax + sline.amount_total)::numeric, 2) amount_total_fix,
                    ROUND(SUM(sline.amount_subtotal - sline.amount_tax - sline.amount_total)::numeric, 2) amount_total_discount
                FROM chariots_import_kfc_sale_line sline
                WHERE sline.date >= '{date_init}' AND sline.date <= '{date_end}' 
                GROUP BY sale_id, tax_id
            ) total ON total.sale_id = s.id 
            WHERE s.date >= '{date_init}' AND s.date <= '{date_end}'
            GROUP BY s.id, s.payment_method_id, s.channel_id, s.store_id, total.tax_id;
        """.format(date_init=date_init, date_end=date_end))
        self._cr.commit()
    
    def _get_query_sale_total_invoice(self, dia, where=''):
        where_clause = "WHERE s.date >= '{dia}' AND s.date <= '{dia}'".format(dia=dia)
        if where:
            where_clause += "{where}".format(where=where)
        return """
            SELECT
                s.store_id,
                s.channel_id,
                s.tax_id,
                ROUND(SUM(s.amount_subtotal)::numeric, 2) amount_subtotal,
                ROUND(SUM(s.amount_tax)::numeric, 2) amount_tax,
                ROUND(SUM(s.amount_total)::numeric, 2) amount_total,
                ROUND(SUM(s.amount_total_fix)::numeric, 2) amount_total_fix
            FROM chariots_import_kfc_sale_tax s 
            {where}
            GROUP BY s.store_id, s.channel_id, s.tax_id;  
        """.format(where=where_clause)

    @api.model
    def generate_invoice(self, date):
        # Tenemos que ordenar las líneas por
        #   1. Cuenta Contable
        #   2. Producto
        #   3. Rango Horario
        #   4. Canal

        tax_count_alert = self.env["chariots.import.kfc.sale.line"].search_count([
            ('tax_id', '=', False),
            ('date', '=', date),
            ('tax', '!=', 0),
        ])

        if tax_count_alert > 0:
            message = "Hay impuestos que no existían de KFC. Para poder solucionar el error <a href='/web#action=360&model=chariots.import.kfc.sale.line&view_type=list&menu_id=157'> ve aquí </a> y activa el filtro de 'IVA Odoo no está Establecido'"
            self.env.ref('chariots_core.kfc_channel').message_post(
                body=message, author_id=2,
                message_type="comment", subtype="mail.mt_comment"
            )

            message = "Al haber impuestos faltantes no se han podido generar las facturas del día {}".format(date)
            self.env.ref('chariots_core.kfc_channel').message_post(
                body=message, author_id=2,
                message_type="comment", subtype="mail.mt_comment"
            )
            message = "Para configurar los impuestos <a href='/web#action=356&model=chariots.import.kfc.tax&view_type=list&menu_id=157'> ve aquí </a> y aplica el filtro 'Impuesto Odoo no establecido'"
            self.env.ref('chariots_core.kfc_channel').message_post(
                body=message, author_id=2,
                message_type="comment", subtype="mail.mt_comment"
            )

            return False

        channel_count_alert = self.env["chariots.import.kfc.sale"].search_count([
            ('date', '=', date),
            '|',
            ('channel_id', '=', False),
            ('channel_id.account_id', '=', False),
        ])

        if channel_count_alert > 0:
            message = "Hay canales que no están establecidos o que no tienen cuenta contable. Para poder solucionar el error <a href='/web?debug=1#action=358&model=chariots.import.kfc.channel&view_type=list&menu_id=157'> ve aquí </a>"
            self.env.ref('chariots_core.kfc_channel').message_post(
                body=message, author_id=2,
                message_type="comment", subtype="mail.mt_comment"
            )
            message = "Al haber canales faltantes no se han podido generar las facturas del día {}".format(date)
            self.env.ref('chariots_core.kfc_channel').message_post(
                body=message, author_id=2,
                message_type="comment", subtype="mail.mt_comment"
            )
            message = "Para comprobar los errores en las ventas con canal no establecido <a href='/web#action=359&model=chariots.import.kfc.sale&view_type=list&menu_id=157'> Abrir aquí </a> y aplica el filtro 'Canal no establecido'"
            self.env.ref('chariots_core.kfc_channel').message_post(
                body=message, author_id=2,
                message_type="comment", subtype="mail.mt_comment"
            )

            data_channels = {}
            sale_without_channel = self.env["chariots.import.kfc.sale"].search_count([
                ('date', '=', date),
                '|',
                ('channel_id', '=', False),
                ('channel_id.account_id', '=', False),
            ])
            if sale_without_channel:
                for sale in sale_without_channel:
                    if sale.canal not in data_channels:
                        data_channels[sale.canal] = {
                            'kfc_id': sale.canal,
                            'account_id': False,
                            'channel_id': sale.channel_id.id if sale.channel_id else False,
                            'name_channel': sale.channel_id.name if sale.channel_id else ''
                        }
                if data_channels:
                    message = ""
                    channel_obj = self.env['chariots.import.kfc.channel']
                    for key, val in data_channels.items():
                        if not val['channel_id']:
                            new_channel = channel_obj.create({
                                'name': 'Canal Indefinido',
                                'external_id': val['kfc_id']
                            })
                            message += "Nuevo canal Nombre: {}, ID KFC: {} sin cuenta contable <br> ".format(new_channel.name, new_channel.external_id)
                        else:
                            if val['channel_id'] and not val['account_id']:
                                message += "El canal {} no tiene una cuenta contable establecida <br>".format(val['name_channel'])

                    self.env.ref('chariots_core.kfc_channel').message_post(
                        body=message, author_id=2,
                        message_type="comment", subtype="mail.mt_comment"
                    )

            return False

        pay_method_count_alert = self.env["chariots.import.kfc.sale"].search_count([
            ('date', '=', date),
            ('payment_method_id', '=', False),
            ('pago','=', 0)
        ])

        if pay_method_count_alert > 0:
            message = "Hay métodos de pago que no estan establecidos. Para poder solucionar el error <a href='/web#action=357&model=chariots.import.kfc.paymethod&view_type=list&menu_id=157'> ve aquí </a>"
            self.env.ref('chariots_core.kfc_channel').message_post(
                body=message, author_id=2,
                message_type="comment", subtype="mail.mt_comment"
            )
            message = "Al haber métodos de pago faltantes no se han podido generar las facturas del día {}".format(date)
            self.env.ref('chariots_core.kfc_channel').message_post(
                body=message, author_id=2,
                message_type="comment", subtype="mail.mt_comment"
            )
            message = "Para comprobar los errores en las ventas con método de pago no establecido y con Pago ID 0 <a href='/web#action=359&model=chariots.import.kfc.sale&view_type=list&menu_id=157'> Abrir aquí </a> y aplica el filtro 'Ventas sin método de pago'"
            self.env.ref('chariots_core.kfc_channel').message_post(
                body=message, author_id=2,
                message_type="comment", subtype="mail.mt_comment"
            )
        
        pay_method_two_count_alert = self.env["chariots.import.kfc.sale"].search_count([
            ('date', '=', date),
            ('payment_method_id', '=', False),
            ('pago','!=', 0)
        ])

        if pay_method_two_count_alert > 0:
            message = "Hay {} ventas con métodos de pago que no hemos podido identificar. Para poder solucionar el error <a href='/web#action=359&model=chariots.import.kfc.sale&view_type=list&menu_id=157'> Abrir aquí </a> y aplica el filtro 'Ventas sin pago pero con ID distinto a 0'"
            self.env.ref('chariots_core.kfc_channel').message_post(
                body=message, author_id=2,
                message_type="comment", subtype="mail.mt_comment"
            )
            message = "Aqui tienes todos los métodos de pago disponibles <a href='/web#action=357&model=chariots.import.kfc.paymethod&view_type=list&menu_id=157'> Abrir aquí </a>"
            self.env.ref('chariots_core.kfc_channel').message_post(
                body=message, author_id=2,
                message_type="comment", subtype="mail.mt_comment"
            )
            message = "Al haber métodos de pago faltantes no se han podido generar las facturas del día {}".format(date)
            self.env.ref('chariots_core.kfc_channel').message_post(
                body=message, author_id=2,
                message_type="comment", subtype="mail.mt_comment"
            )

        product_count_alert = self.env["chariots.import.kfc.sale.line"].search_count([
            ('date', '=', date),
            ('product_id', '=', False),
        ])

        if product_count_alert > 0:
            message = "Hay productos que no existían de KFC. Para poder solucionar el error <a href='/web#action=361&model=chariots.import.kfc.product&view_type=list&menu_id=157'> ve aquí </a> y activa el filtro de 'Sin configurar'"
            self.env.ref('chariots_core.kfc_channel').message_post(
                body=message, author_id=2,
                message_type="comment", subtype="mail.mt_comment"
            )

            message = "Para comprobar los errores en las ventas con producto no establecido <a href='/web#action=360&model=chariots.import.kfc.sale.line&view_type=list&menu_id=157'> Abrir aquí </a> y aplica el filtro 'Producto Odoo no establecido'"
            self.env.ref('chariots_core.kfc_channel').message_post(
                body=message, author_id=2,
                message_type="comment", subtype="mail.mt_comment"
            )

        query = self._get_query_sale_total_invoice(date)
        self._cr.execute(query)
        results = self._cr.dictfetchall()
        data_invoices = {}

        for row in results:
            if row['store_id'] not in data_invoices:
                search_store = self.env['chariots.import.kfc.store'].browse(row['store_id'])
                if not search_store:
                    continue
                data_invoices[row['store_id']] = {
                    'lines': [],
                    'store': search_store,
                    'total': 0.0,
                    'tax': 0.0
                }
            data_invoices[row['store_id']]['lines'].append(row)
            data_invoices[row['store_id']]['total'] += row['amount_total_fix']
            data_invoices[row['store_id']]['tax'] += row['amount_tax']

        for key, dat_inv in data_invoices.items():
            type = 'out_invoice' if dat_inv['total'] > 0.0 else 'out_refund'
            store = dat_inv['store']
            date_list = str(date).split('-')
            day = int(date_list[2])
            if day <= 7:
                date_invoice = "{}-{}-{}".format(date_list[0], date_list[1], '14')
            elif day <= 14:
                date_invoice = "{}-{}-{}".format(date_list[0], date_list[1], '21')
            elif day <= 21:
                date_invoice = "{}-{}-{}".format(date_list[0], date_list[1], '28')
            else:
                last_day_of_month = monthrange(int(date_list[0]), int(date_list[1]))[1]
                date_invoice = "{}-{}-{}".format(date_list[0], date_list[1], str(last_day_of_month))

            before_tickets_count = self.env['chariots.import.kfc.sale'].search_count([
                ('date', '>=', "{}-01-01".format(date_list[0])),
                ('date', '<', str(date)),
                ('store_id', '=', store.id)
            ])
            now_tickets_count = self.env['chariots.import.kfc.sale'].search_count([
                ('date', '=', str(date)),
                ('store_id', '=', store.id)
            ])

            data = {
                'partner_id': store.partner_id.id,
                'invoice_line_ids': [],
                'type': type,
                'is_grouped_invoice': True,
                'date_invoice': date_invoice,
                'date': date_invoice,
                'default_ac_analytic_id': store.analytic_account_id.id if store.analytic_account_id else False,
                'journal_id': 1,
                'real_sale_date': date,
                'serial_tickets_code_sii': "{}{}/{}:{}{}/{}".format(
                    str(date_list[0]),
                    store.analytic_account_id.code.split(' ')[0] if store.analytic_account_id else "",
                    str(before_tickets_count + 1),
                    str(date_list[0]),
                    store.analytic_account_id.code.split(' ')[0] if store.analytic_account_id else "",
                    str(before_tickets_count + now_tickets_count)
                )
            }
            for line in dat_inv['lines']:
                if line['amount_total_fix'] == 0:
                    continue
                channel_id = self.env['chariots.import.kfc.channel'].browse(int(line['channel_id']))
                product_id = self.env['product.product'].search([
                    ('property_account_income_id', '=', channel_id.account_id.id)
                ], limit=1)
                if not product_id:
                    product_id = self.env['product.product'].search([
                        ('barcode', '=', 'producto-kfc-dummy')
                    ], limit=1)
                    if not product_id:
                        logging.info("El Producto con ID {} no existe".format(
                            channel_id.name
                        ))
                    continue
                # TODO: Desc. de línea: Canal - F. Venta Real (al {iva}%)
                data_line = {
                    'account_analytic_id': store.analytic_account_id.id if store.analytic_account_id else False,
                    'product_id': product_id.id,
                    'account_id': channel_id.account_id.id,
                    'quantity': 1.0,
                    'price_unit': line['amount_total_fix'] if type == 'out_invoice' else line['amount_total_fix'] * -1,
                    'invoice_line_tax_ids': [(6, 0, [line['tax_id']])],
                    'name': "{}".format(
                        channel_id.name,
                    ),
                }
                data['invoice_line_ids'].append((0, 0, data_line))
            try:
                inv = self.env['account.invoice'].with_context({
                    'default_type': type,
                    'type': type,
                    'journal_type': 'sale',
                }).create(data)
            except:
                self.env.cr.rollback()
                message = "Ha ocurrido un error no esperado en {} para la fecha {}.".format(
                    store.name,
                    str(date_invoice)
                )
                self.env.ref('chariots_core.kfc_channel').message_post(
                    body=message, author_id=2,
                    message_type="comment", subtype="mail.mt_comment"
                )

            tax_diff = round(abs(dat_inv['tax']), 2) - round(inv.amount_tax, 2)
            if abs(tax_diff) > 0.00:
                major_tax = inv.tax_line_ids.search([
                    ('invoice_id', '=', inv.id)
                ], limit=1, order="amount DESC")
                major_tax.write({
                    'amount': major_tax.amount + tax_diff
                })
            query_is_imported = """
                UPDATE chariots_import_kfc_sale
                SET is_imported = true
                WHERE date = '{date}' AND store_id = {store};
                UPDATE chariots_import_kfc_sale_line
                SET is_imported = true, invoice_id = {inv}
                WHERE date = '{date}' AND store_id = {store};
            """.format(date=date, store=store.id, inv=inv.id)
            self._cr.execute(query_is_imported)
            self._cr.commit()

            query_order = """
                UPDATE chariots_import_kfc_sale_line
                SET invoice_id = {inv}
                WHERE date = '{date}' AND is_imported = false AND store_id = {store};
                SELECT line.id
                FROM account_invoice_line line
                JOIN account_account account ON account.id = line.account_id
                JOIN product_product product ON product.id = line.product_id
                JOIN product_template template ON product.product_tmpl_id = template.id
                WHERE invoice_id = {inv}
                ORDER BY account.name ASC, template.name ASC;
            """.format(inv=inv.id, date=date, store=store.id)
            self._cr.execute(query_order)
            lines_result = self._cr.dictfetchall()
            sequence = 0
            for l in lines_result:
                sequence += 1
                line = self.env['account.invoice.line'].browse(int(l['id']))
                line.write({
                    'sequence': sequence
                })
            self._cr.commit()
            # Generar pagos por metodo de pago
            # inv.generate_payment_by_method()

    @api.model
    def cron_set_code_sii_tickets(self):
        invoices = self.env['account.invoice'].sudo().search([
            ('journal_id', '=', 1),
            ('default_ac_analytic_id', '!=', False),
            '|',
            ('serial_tickets_code_sii', '=', False),
            ('serial_tickets_code_sii', '=', '')
        ])
        for invoice in invoices:
            store = self.env['chariots.import.kfc.store'].sudo().search([
                ('analytic_account_id', '=', invoice.default_ac_analytic_id.id)
            ])
            date = invoice.real_sale_date
            before_tickets_count = self.env['chariots.import.kfc.sale'].search_count([
                ('date', '>=', "{}-01-01".format(str(invoice.real_sale_date.year))),
                ('date', '<', str(date)),
                ('store_id', '=', store.id)
            ])
            now_tickets_count = self.env['chariots.import.kfc.sale'].search_count([
                ('date', '=', str(date)),
                ('store_id', '=', store.id)
            ])
            invoice.write({
                'serial_tickets_code_sii': "{}{}/{}:{}{}/{}".format(
                    str(invoice.real_sale_date.year),
                    store.analytic_account_id.code.split(' ')[0] if store.analytic_account_id else "",
                    str(before_tickets_count + 1),
                    str(invoice.real_sale_date.year),
                    store.analytic_account_id.code.split(' ')[0] if store.analytic_account_id else "",
                    str(before_tickets_count + 1 + now_tickets_count)
                )
            })

    @api.model
    def cron_get_kfc_sale(self, day=False, month=False, year=False, generate=True, sales=True, lines=True,
                          products=True, salefile=False, linefile=False, storeid=False):
        domain = self.env['ir.config_parameter'].get_param('Ftp.domain')
        port = self.env['ir.config_parameter'].get_param('Ftp.port')
        user = self.env['ir.config_parameter'].get_param('Ftp.username')
        passw = self.env['ir.config_parameter'].get_param('Ftp.password')
        local_path = self.env['ir.config_parameter'].get_param('Ftp.local.path')

        ssh_client = paramiko.SSHClient()
        ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        # Hacemos el login de usuario y passwd,
        ssh_client.connect(hostname=str(domain), port=int(port), username=user, password=passw)
        sftp_client = ssh_client.open_sftp()

        kfc_sale_obj = self.env['chariots.import.kfc.sale']
        kfc_sale_line_obj = self.env['chariots.import.kfc.sale.line']
        if not day or not month or not year:
            date_now = datetime.now()
            day = str(date_now.day).zfill(2)
            month = str(date_now.month).zfill(2)
            year = str(date_now.year)
            date_actual = date.today()
            from_date = str(datetime.today() - timedelta(days=8))
        else:
            date_actual = datetime.strptime("{}-{}-{}".format(year, month, day), "%Y-%m-%d").date()
            from_date = str(date_actual - timedelta(days=8))

        # Nombres de los ficheros a buscar
        if sales:
            if not salefile:
                name_file_transaction = "TRANSACCIONES{}{}{}.csv".format(year, month, day)
            else:
                name_file_transaction = salefile
            remote_path_transaction = "./{}".format(name_file_transaction)
            local_path_transaction = "{}/{}".format(local_path, name_file_transaction)
            sftp_client.get(remote_path_transaction, local_path_transaction)

        if lines:
            if not linefile:
                name_file_detail = "DETALLE{}{}{}.csv".format(year, month, day)
            else:
                name_file_detail = linefile
            remote_path_detail = "./{}".format(name_file_detail)
            local_path_detail = "{}/{}".format(local_path, name_file_detail)
            sftp_client.get(remote_path_detail, local_path_detail)

        if products:
            name_file_product = "LK_PRODUCTO{}{}{}.csv".format(year, month, day)
            remote_path_product = "./{}".format(name_file_product)
            local_path_product = "{}/{}".format(local_path, name_file_product)
            sftp_client.get(remote_path_product, local_path_product)

        sftp_client.close()
        ssh_client.close()

        # Crear Adjuntos para Google Drive
        if sales:
            with open(local_path_transaction, "rb") as transaction_binary:
                transaction_b64 = base64.b64encode(transaction_binary.read())
                self.env['ir.attachment'].sudo().create({
                    'name': name_file_transaction,
                    'res_name': name_file_transaction,
                    'folder_id': self.env.ref('chariots_core.folder_kfc').id,
                    'type': 'binary',
                    'datas': transaction_b64
                })
        if lines:
            with open(local_path_detail, "rb") as detail_binary:
                detail_b64 = base64.b64encode(detail_binary.read())
                self.env['ir.attachment'].sudo().create({
                    'name': name_file_detail,
                    'res_name': name_file_detail,
                    'folder_id': self.env.ref('chariots_core.folder_kfc').id,
                    'type': 'binary',
                    'datas': detail_b64
                })
        if products:
            with open(local_path_product, "rb") as product_binary:
                product_b64 = base64.b64encode(product_binary.read())
                self.env['ir.attachment'].sudo().create({
                    'name': name_file_product,
                    'res_name': name_file_product,
                    'folder_id': self.env.ref('chariots_core.folder_kfc').id,
                    'type': 'binary',
                    'datas': product_b64
                })

        today = str(datetime.today())

        query_count = """
            SELECT COUNT(id) cuantos, date
            FROM chariots_import_kfc_sale_line line
            WHERE {} AND date > '{}'
            GROUP BY date;
        """
        self.env.cr.execute(query_count.format("is_imported = true", from_date))
        first_cuantos = {}
        for dia in self.env.cr.dictfetchall():
            first_cuantos[dia['date']] = dia['cuantos']

        if products:
            query = """
                INSERT INTO chariots_import_kfc_product (
                    "external_id", "name", "desc", "create_uid", "create_date", "write_uid", "write_date"
                ) VALUES
            """
            first = True

            with open(local_path_product, newline='', encoding="iso-8859-1") as File:
                reader = csv.reader(File)
                for line in reader:
                    line = line[0].split(';')
                    # Comprobamos que no sea la primera linea
                    if line[0] == 'ID_ARTICULO':
                        continue
                    if first:
                        first = False
                    else:
                        query += ","
                    query += """('{}', '{}', '{}', 1, '{}', 1, '{}')""".format(
                        line[0], clean_txt(line[1]), clean_txt(line[2]) if len(line) > 2 else "",
                        today, today
                    )
                query += " ON CONFLICT ON CONSTRAINT chariots_import_kfc_product_external_id_unique DO NOTHING;"
                if not first:
                    self.env.cr.execute(query)
                    self.env.cr.commit()
                    logging.info("Productos Importados")

        if sales:
            with open(local_path_transaction, newline='') as File:
                reader = csv.reader(File)
                fields = [
                    'external_id', 'date', 'hour', 'store',
                    'canal', 'amount_total', 'amount_subtotal',
                    'amount_tax', 'trans_count', 'n_lineas',
                    'trans_status', 'pago'
                ]
                query_insert = """
                    INSERT INTO chariots_import_kfc_sale (
                        "external_id", "date", "hour", "store", "canal", "amount_total", "amount_subtotal", "amount_tax", "trans_count", "n_lineas", "trans_status", "pago", "write_uid", "create_uid", "write_date", "create_date", "is_imported"
                    ) VALUES
                """
                count = 0
                for line in reader:
                    line = line[0].split(';')
                    # Comprobamos que no sea la primera linea
                    if line[0] == 'ID_TRANSACCION':
                        continue

                    line[1] = line[1][0:10]

                    if storeid and int(line[3]) != storeid:
                        continue

                    if count > 0:
                        query_insert += ","
                    count += 1

                    query_insert += """({}, '{}', '{}', {}, {}, {}, {}, {}, {}, {}, '{}', {}, 1, 1, '{}', '{}', {})""".format(
                        line[0], line[1], line[2], line[3],
                        line[4], line[5], line[6], line[7],
                        line[9], line[10], line[11], line[12],
                        today, today, "false"
                    )
                query_insert += """
                    ON CONFLICT ON CONSTRAINT chariots_import_kfc_sale_external_id_unique
                    DO NOTHING; 
                """
                if count > 0:
                    self.env.cr.execute(query_insert.replace("\n", " "))
                    self.env.cr.commit()
                    kfc_sale_obj.relate_models()
                    logging.info("Ventas Importadas {}".format(count))

        if lines:
            with open(local_path_detail, newline='') as File:
                reader = csv.reader(File)
                fields = [
                    'date', 'store', 'sale', 'external_id',
                    'product', 'product_parent', 'category', 'category_name',
                    'qty', 'unit_amount_subtotal', 'unit_amount_total', 'unit_amount_tax',
                    'tax', 'amount_total', 'amount_subtotal', 'amount_tax'
                ]
                query_insert = """
                    INSERT INTO chariots_import_kfc_sale_line (
                        "date", "store", "sale", "external_id", "product", "product_parent", "category", "category_name", "qty", "unit_amount_subtotal", "unit_amount_total", "unit_amount_tax", "tax", "amount_total", "amount_subtotal", "amount_tax", "write_uid", "create_uid", "write_date", "create_date", "is_imported"
                    ) VALUES
                """
                count = 0
                for line in reader:
                    line = line[0].split(';')
                    # Comprobamos que no sea la primera linea
                    if line[0] == 'FECHA':
                        continue

                    line[0] = line[0][0:10]

                    if storeid and int(line[1]) != storeid:
                        continue

                    if count > 0:
                        query_insert += ","
                    count += 1

                    query_insert += """('{}', {}, {}, {}, {}, {}, {}, '{}', {}, {}, {}, {}, {}, {}, {}, {}, 1, 1, '{}', '{}', {})""".format(
                        line[0], line[1], line[2], line[3],
                        line[4], line[5], line[6], clean_txt(line[7]),
                        line[8], line[9], line[10], line[11],
                        line[12], line[13], line[14], line[15],
                        today, today, "false"
                    )

                query_insert += """
                    ON CONFLICT ON CONSTRAINT chariots_import_kfc_sale_line_external_id_unique
                    DO UPDATE SET amount_total = EXCLUDED.amount_total, amount_subtotal = EXCLUDED.amount_subtotal, amount_tax = EXCLUDED.amount_tax;
                """
                if count > 0:
                    self.env.cr.execute(query_insert.replace("\n", " "))
                    self.env.cr.commit()
                    kfc_sale_line_obj.relate_models()
                    logging.info("Líneas Importadas {}".format(count))

        if generate:
            self.env.cr.execute(query_count.format("1 = 1", from_date))
            for dia in self.env.cr.dictfetchall():
                if dia['date'] not in first_cuantos:
                    kfc_sale_obj.cron_compute_sale_amounts(date_init=dia['date'], date_end=dia['date'])
                    kfc_sale_obj.generate_invoice(date=dia['date'])
                    logging.info("Generando factura del día {} porque no existía".format(dia['date']))
                elif dia['cuantos'] != first_cuantos[dia['date']]:
                    kfc_sale_obj.cron_compute_sale_amounts(date_init=dia['date'], date_end=dia['date'])
                    kfc_sale_obj.generate_invoice(date=dia['date'])
                    logging.info("Generando factura del día {} por diferencias".format(dia['date']))

    # Para enviar correo de venta diario
    @api.multi
    def cron_send_email_kfc_sale_daily(self):
        kfc_sale_obj = self.env[self._name]
        kfc_store_obj = self.env['chariots.import.kfc.store']
        template_email = self.env.ref('chariots_core.format_kfc_sale_email')
        email_server_obj = self.env['ir.mail_server']
        no_sales = []
        date_actual = datetime.now()
        date_actual = (date_actual - timedelta(days=1))
        months = [
            'Enero', 'Febrero', 'Marzo', 'Abril',
            'Mayo', 'Junio', 'Julio', 'Agosto',
            'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'
        ]
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
        WHERE sale.date = '{}-{}-{}'
        GROUP BY store.id, sale.date, is_imported
        ORDER BY name ASC, sale.date 
    """.format(str(date_actual.year), str(date_actual.month).zfill(2), str(date_actual.day).zfill(2))
        kfc_sale_obj._cr.execute(query_kfc)
        results_kfc_sale = kfc_sale_obj._cr.fetchall()
        if results_kfc_sale:
            totals = {'amount_total_total': 0, 'sale_medium': 0, 'invoices_generated': 0, 'num_sales': 0,
                      'errors': 0}
            stores_list = []
            text_tbody = ""
            for store_id, name, num_sales, amount_total_total, sale_medium, is_imported in results_kfc_sale:
                count_errors = self.env["chariots.import.kfc.sale.line"].search_count([
                    ('product_id', '=', False),
                    ('date', '=', date_actual),
                    ('store_id', '=', store_id)
                ])
                store = kfc_store_obj.search([('id', '=', store_id)])
                stores_list.append(store_id)
                text_tbody += """
                <tr>
                    <td style="height:40px;border:1px solid black;border-collapse:collapse;text-align:left;">{name}</td>
                    <td style="height:40px;border:1px solid black;border-collapse:collapse;text-align:center;">{tickets}</td>
                    <td style="height:40px;border:1px solid black;border-collapse:collapse;text-align:center;">{total} {symbol}</td>
                    <td style="height:40px;border:1px solid black;border-collapse:collapse;text-align:center;">{tmedio} {symbol}</td>
                    <td style="height:40px;border:1px solid black;border-collapse:collapse;text-align:center;">{invoice}</td>
                    <td style="height:40px;border:1px solid black;border-collapse:collapse;text-align:center;"><strong>{errors}</strong></td>
                </tr>
                """.format(
                    name=store.analytic_account_id.name,
                    tickets=str(num_sales),
                    total="{0:.2f}".format(round(amount_total_total, 2)),
                    tmedio="{0:.2f}".format(round(sale_medium, 2)),
                    symbol=self.env.user.company_id.currency_id.symbol,
                    invoice="Sí" if is_imported else "No",
                    errors=str(count_errors)

                )
                totals['num_sales'] += num_sales
                totals['sale_medium'] += round(sale_medium, 2)
                totals['amount_total_total'] += round(amount_total_total, 2)
                totals['invoices_generated'] += 1 if is_imported else 0
                totals['errors'] += count_errors

            all_stores = kfc_store_obj.search([('id', '!=', stores_list)])
            for store in all_stores:
                no_sales.append({'store': store, 'date': date_actual})
                text_tbody += """
                <tr>
                    <td style="height:40px;border:1px solid black;border-collapse:collapse;text-align:left;">{name}</td>
                    <td style="height:40px;border:1px solid black;border-collapse:collapse;text-align:center;">0</td>
                    <td style="height:40px;border:1px solid black;border-collapse:collapse;"></td>
                    <td style="height:40px;border:1px solid black;border-collapse:collapse;"></td>
                    <td style="height:40px;border:1px solid black;border-collapse:collapse;text-align:center;">{invoice}</td>
                    <td style="height:40px;border:1px solid black;border-collapse:collapse;text-align:center;"><strong>0</strong></td>
                </tr>
            """.format(
                    name=store.analytic_account_id.name,
                    invoice="No"
                )
            text_tbody += """
                <tr>
                    <td style="height:40px;border:1px solid black;border-collapse:collapse;text-align:left;"><strong>TOTALES</strong></td>
                    <td style="height:40px;border:1px solid black;border-collapse:collapse;text-align:center;"><strong>{tickets}</strong></td>
                    <td style="height:40px;border:1px solid black;border-collapse:collapse;text-align:center;"><strong>{total} {symbol}</strong></td>
                    <td style="height:40px;border:1px solid black;border-collapse:collapse;text-align:center;"><strong>{tmedio} {symbol}</strong></td>
                    <td style="height:40px;border:1px solid black;border-collapse:collapse;text-align:center;"><strong>{invoice}</strong></td>
                    <td style="height:40px;border:1px solid black;border-collapse:collapse;text-align:center;"><strong>{errors}</strong></td>

                </tr>
            """.format(
                tickets=str(totals['num_sales']),
                total="{0:.2f}".format(totals['amount_total_total']),
                tmedio="{0:.2f}".format(round(float(totals['sale_medium'] / totals['invoices_generated']), 2)) if
                totals['invoices_generated'] > 0 else "{0:.2f}".format(0),
                symbol=self.env.user.company_id.currency_id.symbol,
                invoice=str(totals['invoices_generated']),
                errors=str(totals['errors'])

            )
            text_email = """
            Buenas {},<br /> Aquí tienes el resumen del día de todos los centros:<br />
            <table style="width:50%;border:1px solid black;border-collapse:collapse;">
                <tr>
                    <th style="border:1px solid black;border-collapse:collapse;">Centro</th>
                    <th style="border:1px solid black;border-collapse:collapse;">Nº Tickets</th>
                    <th style="border:1px solid black;border-collapse:collapse;">Total de Ventas</th>
                    <th style="border:1px solid black;border-collapse:collapse;">Ticket Medio</th>
                    <th style="border:1px solid black;border-collapse:collapse;">Factura Generada</th>
                    <th style="border:1px solid black;border-collapse:collapse;">Errores</th>

                </tr>
                {}
            </table>
            <br/>
            Un saludo
        """.format(self.env.user.company_id.name, text_tbody)
        # Si ningun centro ha realizado ninguna venta a lo largo del día se lo comunicamos igualmente
        else:
            all_stores = kfc_store_obj.search([])
            for store in all_stores:
                no_sales.append({'store': store, 'date': date_actual})

            text_email = """
            Buenas {},<br /> Ayer ningún centro realizó ninguna venta.
            <br />
            Un saludo
        """.format(
                self.env.user.company_id.name
            )
        email_server = email_server_obj.search([], limit=1)
        if not email_server:
            logging.error('No hay ningún servidor de email tenemos que añadirlo')

        values_email = {
            'subject': "Resumen de Ventas de KFC {} de {} del {}".format(
                str(date_actual.day).zfill(2),
                months[date_actual.month - 1],
                date_actual.year
            ),
            'body_html': text_email,
            'email_to': '',
            'email_from': email_server.smtp_user
        }
        base_group_system = self.env.ref('base.group_system')
        email_to = ''
        for user in base_group_system.users:
            if user.partner_id.email:
                email_to += user.partner_id.email + ','
        values_email['email_to'] = email_to
        if template_email:
            last_sale = kfc_sale_obj.search([], limit=1, order='date DESC')
            template_email.send_mail(last_sale.id, force_send=True, email_values=values_email)

        if no_sales:
            kfc_sale_obj.new_sales(no_sales)

    def new_sales(self, no_sales):
        obj = self.env[self._name]
        for no_sale in no_sales:
            st = no_sale['store']
            dat = no_sale['date']
            new_sale = {
                'external_id': 0,
                'date': dat,
                'store': st.external_id,
                'is_imported': True,
                'store_id': st.id,
                'line_ids': [(0, 0, {
                    'date': dat,
                    'store': st.external_id,
                    'unit_amount_total': 0,
                    'unit_amount_subtotal': 0,
                    'unit_amount_tax': 0,
                    'amount_total': 0,
                    'amount_subtotal': 0,
                    'amount_tax': 0,
                    'discount': 0,
                    'store_id': st.id,
                    'is_imported': True,
                    'qty': 0

                })]
            }
            obj.create(new_sale)

    def query_kfc_sale_report(self):
        select_fields = """
        SELECT
            kfc_sale_line.id,
            kfc_sale_line.date as date,
            SUM(kfc_sale_line.qty) as qty,
            SUM(kfc_sale_line.amount_subtotal) as amount_subtotal,
            SUM(kfc_sale_line.amount_total) as amount_total,
            SUM(kfc_sale_line.amount_tax) as amount_tax,
            SUM(kfc_sale_line.unit_amount_total) as unit_amount_total,
            SUM(kfc_sale_line.unit_amount_subtotal) as unit_amount_subtotal,
            SUM(kfc_sale_line.unit_amount_tax) as unit_amount_tax,
            kfc_store.id as store_id,
            kfc_channel.id as channel_id,
            kfc_paymethod.id as payment_method_id,
            kfc_range.id as range_id,
            kfc_sale.id as sale_id,
            kfc_sale_line.category_name as category_name

        """
        join_fields = """
        FROM chariots_import_kfc_sale_line AS kfc_sale_line
            JOIN chariots_import_kfc_store AS kfc_store ON (kfc_sale_line.store = kfc_store.external_id)
            JOIN chariots_import_kfc_sale AS kfc_sale ON (kfc_sale_line.sale_id = kfc_sale.id)
            LEFT JOIN chariots_import_kfc_channel AS kfc_channel ON (kfc_sale.channel_id = kfc_channel.id)                
            LEFT JOIN chariots_import_kfc_paymethod AS kfc_paymethod ON (kfc_sale.payment_method_id = kfc_paymethod.id)                
            LEFT JOIN chariots_import_kfc_timerange AS kfc_range ON (kfc_sale.range_id = kfc_range.id)                
        """
        group_order = """
        GROUP BY
            kfc_sale_line.id,
            kfc_store.name, 
            kfc_store.id,
            kfc_channel.id, 
            kfc_paymethod.id,
            kfc_range.id,
            kfc_sale.id,
            kfc_sale_line.category_name

        """
        query_complete = select_fields + join_fields + group_order
        return query_complete


class KfcSaleTax(models.Model):
    _name = "chariots.import.kfc.sale.tax"
    _description = "Chariots: Impuestos de Ventas de KFC"

    date = fields.Date(
        string="Fecha de Venta"
    )
    store_id = fields.Many2one(
        comodel_name="chariots.import.kfc.store",
        string="Tienda"
    )
    sale_id = fields.Many2one(
        comodel_name="chariots.import.kfc.sale",
        string="Venta",
    )
    tax_id = fields.Many2one(
        comodel_name="account.tax",
        string="Impuesto Odoo",
    )
    amount_subtotal = fields.Float(
        string="Total Real",
    )
    amount_tax = fields.Float(
        string="Impuesto",
    )
    amount_total = fields.Float(
        string="Base",
    )
    amount_total_fix = fields.Float(
        string="Total",
    )
    payment_method_id = fields.Many2one(
        comodel_name="chariots.import.kfc.paymethod",
        string="Método de pago de Venta ",
    )
    channel_id = fields.Many2one(
        comodel_name="chariots.import.kfc.channel",
        string="Canal de Venta",
    )


class KfcSaleLine(models.Model):
    _name = "chariots.import.kfc.sale.line"
    _description = "Chariots: Línea de Ventas de KFC"

    _sql_constraints = [
        ('external_id_unique', 'unique (external_id,date,store)', 'External ID ya existente.')
    ]

    name = fields.Char(
        string="Nombre",
        compute="_compute_name"
    )
    external_id = fields.Integer(
        string="ID KFC"
    )
    date = fields.Date(
        string="Fecha"
    )
    store = fields.Integer(
        string="Tienda ID"
    )
    sale = fields.Integer(
        string="Venta ID"
    )
    product = fields.Integer(
        string="Producto ID"
    )
    product_parent = fields.Integer(
        string="Produto Padre ID"
    )
    category = fields.Integer(
        string="Categoría ID"
    )
    category_name = fields.Char(
        string="Nombre de Categoría"
    )
    qty = fields.Integer(
        string="Cantidad"
    )
    unit_amount_total = fields.Float(
        string="Valor unitario neto"
    )
    unit_amount_subtotal = fields.Float(
        string="Valor unitario bruto"
    )
    unit_amount_tax = fields.Float(
        string="Valor unitario impuestos"
    )
    tax = fields.Integer(
        string="Impuesto ID"
    )
    discount = fields.Float(
        string="Descuento"
    )
    amount_total = fields.Float(
        string="Neto"
    )
    amount_subtotal = fields.Float(
        string="Bruto"
    )
    amount_tax = fields.Float(
        string="Impuestos"
    )
    sale_id = fields.Many2one(
        comodel_name="chariots.import.kfc.sale",
        string="Venta",
        ondelete="cascade",
        index=True
    )
    store_id = fields.Many2one(
        comodel_name="chariots.import.kfc.store",
        string="Tienda"
    )
    kfc_product_id = fields.Many2one(
        comodel_name="chariots.import.kfc.product",
        string="Producto KFC"
    )
    kfc_parent_product_id = fields.Many2one(
        comodel_name="chariots.import.kfc.product",
        string="Producto Padre KFC"
    )
    product_id = fields.Many2one(
        comodel_name="product.product",
        string="Producto Odoo"
    )
    kfc_tax_id = fields.Many2one(
        comodel_name="chariots.import.kfc.tax",
        string="Impuesto KFC"
    )
    tax_id = fields.Many2one(
        comodel_name="account.tax",
        string="Impuesto Odoo"
    )
    is_imported = fields.Boolean(
        string="¿Ha sido importada?",
        default=False
    )
    invoice_id = fields.Many2one(
        string="Factura",
        comodel_name="account.invoice",
        index=True
    )

    total_net = fields.Float(
        string="Total Neto"
    )

    @api.multi
    def _compute_name(self):
        for sale_line in self:
            sale_line.name = "Línea {} de {} en {}".format(sale_line.external_id, sale_line.sale,
                                                           str(sale_line.date))

    @api.model
    def relate_models(self):
        query = """
        UPDATE chariots_import_kfc_sale_line AS line
            SET store_id = x.id
            FROM chariots_import_kfc_store x
            WHERE x.external_id = line.store AND line.is_imported = false;
        UPDATE chariots_import_kfc_sale_line AS line
            SET sale_id = x.id
            FROM chariots_import_kfc_sale x
            WHERE x.external_id = line.sale AND x.store = line.store AND x.date = line.date AND line.is_imported = false;
        UPDATE chariots_import_kfc_sale_line AS line
            SET kfc_product_id = x.id, product_id = x.product_id 
            FROM chariots_import_kfc_product x
            WHERE x.external_id = line.product AND line.is_imported = false;
        UPDATE chariots_import_kfc_sale_line AS line
            SET kfc_parent_product_id = x.id 
            FROM chariots_import_kfc_product x
            WHERE x.external_id = line.product_parent AND line.is_imported = false;
        UPDATE chariots_import_kfc_sale_line AS line
            SET kfc_tax_id = x.id, tax_id = x.tax_id
            FROM chariots_import_kfc_tax x
            WHERE x.external_id = line.tax AND line.is_imported = false;
    """
        self.env.cr.execute(query)
        self.env.cr.commit()
