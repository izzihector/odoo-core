SELECT account_payment.id pid, account_invoice.id iid
FROM account_payment
       JOIN account_invoice
            ON account_invoice.amount_total = account_payment.amount AND
               account_invoice.partner_id = account_payment.partner_id
       LEFT JOIN account_invoice_payment_rel aipr on account_invoice.id = aipr.invoice_id
WHERE aipr.invoice_id IS NULL
  AND account_payment.payment_date > account_invoice.date_invoice;