SELECT MAX(aml.analytic_account_id), aml.move_id
FROM account_move_line aml
WHERE date >= '2020-01-01'
  AND analytic_account_id IS NOT NULL
GROUP BY aml.move_id
HAVING COUNT(DISTINCT aml.analytic_account_id) = 1;

UPDATE account_move_line
SET analytic_account_id = t1.analytic_account_id
FROM (
         SELECT MAX(aml.analytic_account_id) analytic_account_id, aml.move_id
         FROM account_move_line aml
         WHERE date >= '2020-01-01'
           AND analytic_account_id IS NOT NULL
         GROUP BY aml.move_id
         HAVING COUNT(DISTINCT aml.analytic_account_id) = 1
     ) as t1
WHERE t1.move_id = account_move_line.move_id AND account_move_line.analytic_account_id IS NULL AND date >= '2020-01-01';