UPDATE res_partner
set payment_origin_sel = 'bank_transfer'
where payment_origin ilike 'Bank transfer';

UPDATE res_partner
set payment_origin_sel = 'direct_debit'
where payment_origin ilike 'Direct debit';