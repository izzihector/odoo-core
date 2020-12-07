UPDATE account_invoice
SET partner_bank_id = t1.bank_id
FROM (
       SELECT res_partner_bank.partner_id, MIN(res_partner_bank.id) bank_id
       FROM res_partner_bank
       GROUP BY res_partner_bank.partner_id
     ) t1
WHERE account_invoice.partner_id = t1.partner_id
  AND partner_bank_id IS NULL
  AND type IN ('in_invoice', 'out_refund');