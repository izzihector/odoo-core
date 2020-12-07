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
WHERE s.id = sline.sale_id 