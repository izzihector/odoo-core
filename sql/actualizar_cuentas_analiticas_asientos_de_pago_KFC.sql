UPDATE account_move_line as mv_l SET
analytic_account_id = res.default_ac_analytic_id 
FROM (SELECT inv.default_ac_analytic_id as default_ac_analytic_id, inv.move_payment_id as move_id
    FROM account_invoice as inv
    WHERE inv.move_payment_id is not NULL and inv.default_ac_analytic_id is not NULL and inv.journal_id = 1 and date_invoice >= '2020-01-01') res
WHERE mv_l.move_id = res.move_id and mv_l.journal_id = 53 and date >= '2020-01-01'