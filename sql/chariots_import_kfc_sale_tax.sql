DELETE FROM chariots_import_kfc_sale_tax;

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
    WHERE sline.date >= '2020-01-01' AND sline.date <= '2020-10-31' 
    GROUP BY sale_id, tax_id
) total ON total.sale_id = s.id 
WHERE s.date >= '2020-01-01' AND s.date <= '2020-10-31'
GROUP BY s.id, s.payment_method_id, s.channel_id, s.store_id, total.tax_id;