UPDATE chariots_import_kfc_sale_line line
SET invoice_id = inv.id
FROM account_invoice inv, chariots_import_kfc_store store
WHERE
  line.store_id = store.id AND
  line.date = inv.real_sale_date AND
  store.analytic_account_id = inv.default_ac_analytic_id;