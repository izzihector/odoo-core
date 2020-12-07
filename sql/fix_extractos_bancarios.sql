UPDATE account_bank_statement_line
SET sequence = 0;
UPDATE account_bank_statement_line
SET sequence = 55
FROM (
       SELECT amount, ref, journal_id, date
       FROM account_bank_statement_line
       GROUP BY amount, ref, journal_id, date
       HAVING COUNT(id) > 1
     ) t1
WHERE t1.amount = account_bank_statement_line.amount
  AND t1.ref = account_bank_statement_line.ref
  AND t1.date = account_bank_statement_line.date
  AND t1.journal_id = account_bank_statement_line.journal_id;