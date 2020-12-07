import logging
_logger = logging.getLogger(__name__)
from odoo import models, fields, api, tools


class KFCSaleReport(models.Model):

    _name = 'kfc.sale.report'
    _description = "Reporte: Ventas de KFC"
    _auto = False


    sale_id = fields.Many2one('chariots.import.kfc.sale', string='Venta', readonly=True)
    store_id = fields.Many2one('chariots.import.kfc.store', string='Tienda', readonly=True)
    channel_id = fields.Many2one('chariots.import.kfc.channel', string='Canal', readonly=True)
    range_id = fields.Many2one('chariots.import.kfc.timerange', string='Rango Horario', readonly=True)
    payment_method_id = fields.Many2one('chariots.import.kfc.paymethod', string='Pago', readonly=True)
    qty = fields.Integer(string='Cantidad', readonly=True)
    date = fields.Date(string='Fecha', readonly=True)
    unit_amount_subtotal = fields.Float(string='Valor unitario bruto', readonly=True)
    unit_amount_total = fields.Float(string='Valor unitario neto', readonly=True)
    unit_amount_tax = fields.Float(string='Valor unitatrio impuestos', readonly=True)
    amount_subtotal = fields.Float(string='Bruto', readonly=True)
    amount_tax = fields.Float(string='Impuestos', readonly=True)
    amount_total = fields.Float(string='Neto', readonly=True)
    category_name = fields.Char(string='Categoría', readonly=True)

    
    _order = 'date desc'
    
    @api.model_cr
    def init(self):
        tools.drop_view_if_exists(self._cr, self._table)
        query_kfc_sale_report = self.env['chariots.import.kfc.sale'].query_kfc_sale_report()
        self._cr.execute("""CREATE OR REPLACE VIEW %s AS (
            %s

            )""" % (self._table, query_kfc_sale_report))

