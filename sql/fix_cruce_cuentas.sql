UPDATE account_invoice_line
SET account_analytic_id = 1
WHERE account_analytic_id = 27
  AND id IN (
  SELECT l.id
  FROM account_invoice_line l
         JOIN account_analytic_account a ON a.id = l.account_analytic_id
  WHERE a.company_id != l.company_id
);

UPDATE account_invoice_line
SET account_analytic_id = 2
WHERE account_analytic_id = 28
  AND id IN (
  SELECT l.id
  FROM account_invoice_line l
         JOIN account_analytic_account a ON a.id = l.account_analytic_id
  WHERE a.company_id != l.company_id
);

UPDATE account_invoice_line
SET account_analytic_id = 3
WHERE account_analytic_id = 29
  AND id IN (
  SELECT l.id
  FROM account_invoice_line l
         JOIN account_analytic_account a ON a.id = l.account_analytic_id
  WHERE a.company_id != l.company_id
);

UPDATE account_invoice_line
SET account_analytic_id = 4
WHERE account_analytic_id = 30
  AND id IN (
  SELECT l.id
  FROM account_invoice_line l
         JOIN account_analytic_account a ON a.id = l.account_analytic_id
  WHERE a.company_id != l.company_id
);

UPDATE account_invoice_line
SET account_analytic_id = 5
WHERE account_analytic_id = 31
  AND id IN (
  SELECT l.id
  FROM account_invoice_line l
         JOIN account_analytic_account a ON a.id = l.account_analytic_id
  WHERE a.company_id != l.company_id
);

UPDATE account_invoice_line
SET account_analytic_id = 6
WHERE account_analytic_id = 32
  AND id IN (
  SELECT l.id
  FROM account_invoice_line l
         JOIN account_analytic_account a ON a.id = l.account_analytic_id
  WHERE a.company_id != l.company_id
);


UPDATE account_invoice_line
SET account_analytic_id = 7
WHERE account_analytic_id = 33
  AND id IN (
  SELECT l.id
  FROM account_invoice_line l
         JOIN account_analytic_account a ON a.id = l.account_analytic_id
  WHERE a.company_id != l.company_id
);


UPDATE account_invoice_line
SET account_analytic_id = 8
WHERE account_analytic_id = 34
  AND id IN (
  SELECT l.id
  FROM account_invoice_line l
         JOIN account_analytic_account a ON a.id = l.account_analytic_id
  WHERE a.company_id != l.company_id
);


UPDATE account_invoice_line
SET account_analytic_id = 9
WHERE account_analytic_id = 35
  AND id IN (
  SELECT l.id
  FROM account_invoice_line l
         JOIN account_analytic_account a ON a.id = l.account_analytic_id
  WHERE a.company_id != l.company_id
);


UPDATE account_invoice_line
SET account_analytic_id = 10
WHERE account_analytic_id = 36
  AND id IN (
  SELECT l.id
  FROM account_invoice_line l
         JOIN account_analytic_account a ON a.id = l.account_analytic_id
  WHERE a.company_id != l.company_id
);


UPDATE account_invoice_line
SET account_analytic_id = 11
WHERE account_analytic_id = 37
  AND id IN (
  SELECT l.id
  FROM account_invoice_line l
         JOIN account_analytic_account a ON a.id = l.account_analytic_id
  WHERE a.company_id != l.company_id
);


UPDATE account_invoice_line
SET account_analytic_id = 12
WHERE account_analytic_id = 38
  AND id IN (
  SELECT l.id
  FROM account_invoice_line l
         JOIN account_analytic_account a ON a.id = l.account_analytic_id
  WHERE a.company_id != l.company_id
);


UPDATE account_invoice_line
SET account_analytic_id = 23
WHERE account_analytic_id = 39
  AND id IN (
  SELECT l.id
  FROM account_invoice_line l
         JOIN account_analytic_account a ON a.id = l.account_analytic_id
  WHERE a.company_id != l.company_id
);

UPDATE account_invoice
SET default_ac_analytic_id = 1
WHERE default_ac_analytic_id = 27
  AND id IN (
  SELECT l.id
  FROM account_invoice l
         JOIN account_analytic_account a ON a.id = l.default_ac_analytic_id
  WHERE a.company_id != l.company_id
);

UPDATE account_invoice
SET default_ac_analytic_id = 2
WHERE default_ac_analytic_id = 28
  AND id IN (
  SELECT l.id
  FROM account_invoice l
         JOIN account_analytic_account a ON a.id = l.default_ac_analytic_id
  WHERE a.company_id != l.company_id
);

UPDATE account_invoice
SET default_ac_analytic_id = 3
WHERE default_ac_analytic_id = 29
  AND id IN (
  SELECT l.id
  FROM account_invoice l
         JOIN account_analytic_account a ON a.id = l.default_ac_analytic_id
  WHERE a.company_id != l.company_id
);

UPDATE account_invoice
SET default_ac_analytic_id = 4
WHERE default_ac_analytic_id = 30
  AND id IN (
  SELECT l.id
  FROM account_invoice l
         JOIN account_analytic_account a ON a.id = l.default_ac_analytic_id
  WHERE a.company_id != l.company_id
);

UPDATE account_invoice
SET default_ac_analytic_id = 5
WHERE default_ac_analytic_id = 31
  AND id IN (
  SELECT l.id
  FROM account_invoice l
         JOIN account_analytic_account a ON a.id = l.default_ac_analytic_id
  WHERE a.company_id != l.company_id
);

UPDATE account_invoice
SET default_ac_analytic_id = 6
WHERE default_ac_analytic_id = 32
  AND id IN (
  SELECT l.id
  FROM account_invoice l
         JOIN account_analytic_account a ON a.id = l.default_ac_analytic_id
  WHERE a.company_id != l.company_id
);

UPDATE account_invoice
SET default_ac_analytic_id = 7
WHERE default_ac_analytic_id = 33
  AND id IN (
  SELECT l.id
  FROM account_invoice l
         JOIN account_analytic_account a ON a.id = l.default_ac_analytic_id
  WHERE a.company_id != l.company_id
);

UPDATE account_invoice
SET default_ac_analytic_id = 8
WHERE default_ac_analytic_id = 34
  AND id IN (
  SELECT l.id
  FROM account_invoice l
         JOIN account_analytic_account a ON a.id = l.default_ac_analytic_id
  WHERE a.company_id != l.company_id
);

UPDATE account_invoice
SET default_ac_analytic_id = 9
WHERE default_ac_analytic_id = 35
  AND id IN (
  SELECT l.id
  FROM account_invoice l
         JOIN account_analytic_account a ON a.id = l.default_ac_analytic_id
  WHERE a.company_id != l.company_id
);

UPDATE account_invoice
SET default_ac_analytic_id = 10
WHERE default_ac_analytic_id = 36
  AND id IN (
  SELECT l.id
  FROM account_invoice l
         JOIN account_analytic_account a ON a.id = l.default_ac_analytic_id
  WHERE a.company_id != l.company_id
);

UPDATE account_invoice
SET default_ac_analytic_id = 11
WHERE default_ac_analytic_id = 37
  AND id IN (
  SELECT l.id
  FROM account_invoice l
         JOIN account_analytic_account a ON a.id = l.default_ac_analytic_id
  WHERE a.company_id != l.company_id
);

UPDATE account_invoice
SET default_ac_analytic_id = 12
WHERE default_ac_analytic_id = 38
  AND id IN (
  SELECT l.id
  FROM account_invoice l
         JOIN account_analytic_account a ON a.id = l.default_ac_analytic_id
  WHERE a.company_id != l.company_id
);

UPDATE account_invoice
SET default_ac_analytic_id = 23
WHERE default_ac_analytic_id = 39
  AND id IN (
  SELECT l.id
  FROM account_invoice l
         JOIN account_analytic_account a ON a.id = l.default_ac_analytic_id
  WHERE a.company_id != l.company_id
);


UPDATE account_invoice_tax
SET account_analytic_id = 1
WHERE account_analytic_id = 27
  AND id IN (
  SELECT l.id
  FROM account_invoice_tax l
         JOIN account_analytic_account a ON a.id = l.account_analytic_id
  WHERE a.company_id != l.company_id
);

UPDATE account_invoice_tax
SET account_analytic_id = 2
WHERE account_analytic_id = 28
  AND id IN (
  SELECT l.id
  FROM account_invoice_tax l
         JOIN account_analytic_account a ON a.id = l.account_analytic_id
  WHERE a.company_id != l.company_id
);

UPDATE account_invoice_tax
SET account_analytic_id = 3
WHERE account_analytic_id = 29
  AND id IN (
  SELECT l.id
  FROM account_invoice_tax l
         JOIN account_analytic_account a ON a.id = l.account_analytic_id
  WHERE a.company_id != l.company_id
);

UPDATE account_invoice_tax
SET account_analytic_id = 4
WHERE account_analytic_id = 30
  AND id IN (
  SELECT l.id
  FROM account_invoice_tax l
         JOIN account_analytic_account a ON a.id = l.account_analytic_id
  WHERE a.company_id != l.company_id
);

UPDATE account_invoice_tax
SET account_analytic_id = 5
WHERE account_analytic_id = 31
  AND id IN (
  SELECT l.id
  FROM account_invoice_tax l
         JOIN account_analytic_account a ON a.id = l.account_analytic_id
  WHERE a.company_id != l.company_id
);

UPDATE account_invoice_tax
SET account_analytic_id = 6
WHERE account_analytic_id = 32
  AND id IN (
  SELECT l.id
  FROM account_invoice_tax l
         JOIN account_analytic_account a ON a.id = l.account_analytic_id
  WHERE a.company_id != l.company_id
);

UPDATE account_invoice_tax
SET account_analytic_id = 7
WHERE account_analytic_id = 33
  AND id IN (
  SELECT l.id
  FROM account_invoice_tax l
         JOIN account_analytic_account a ON a.id = l.account_analytic_id
  WHERE a.company_id != l.company_id
);

UPDATE account_invoice_tax
SET account_analytic_id = 8
WHERE account_analytic_id = 34
  AND id IN (
  SELECT l.id
  FROM account_invoice_tax l
         JOIN account_analytic_account a ON a.id = l.account_analytic_id
  WHERE a.company_id != l.company_id
);

UPDATE account_invoice_tax
SET account_analytic_id = 9
WHERE account_analytic_id = 35
  AND id IN (
  SELECT l.id
  FROM account_invoice_tax l
         JOIN account_analytic_account a ON a.id = l.account_analytic_id
  WHERE a.company_id != l.company_id
);

UPDATE account_invoice_tax
SET account_analytic_id = 10
WHERE account_analytic_id = 36
  AND id IN (
  SELECT l.id
  FROM account_invoice_tax l
         JOIN account_analytic_account a ON a.id = l.account_analytic_id
  WHERE a.company_id != l.company_id
);

UPDATE account_invoice_tax
SET account_analytic_id = 11
WHERE account_analytic_id = 37
  AND id IN (
  SELECT l.id
  FROM account_invoice_tax l
         JOIN account_analytic_account a ON a.id = l.account_analytic_id
  WHERE a.company_id != l.company_id
);

UPDATE account_invoice_tax
SET account_analytic_id = 12
WHERE account_analytic_id = 38
  AND id IN (
  SELECT l.id
  FROM account_invoice_tax l
         JOIN account_analytic_account a ON a.id = l.account_analytic_id
  WHERE a.company_id != l.company_id
);

UPDATE account_invoice_tax
SET account_analytic_id = 23
WHERE account_analytic_id = 39
  AND id IN (
  SELECT l.id
  FROM account_invoice_tax l
         JOIN account_analytic_account a ON a.id = l.account_analytic_id
  WHERE a.company_id != l.company_id
);
