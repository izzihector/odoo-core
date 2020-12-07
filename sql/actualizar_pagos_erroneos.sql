-- Primero solucionamos los asientos contables más evidentes
--- Para eso borramos conciliaciones
DELETE
FROM account_partial_reconcile
WHERE debit_move_id IN (
  SELECT id
  FROM account_move_line
  WHERE move_id IN (
    SELECT MIN(id) AS id
    FROM account_move
    WHERE move_type IN ('liquidity')
    GROUP BY amount, journal_id, date, ref
    HAVING COUNT(id) > 1
  )
)
   OR credit_move_id IN (
  SELECT id
  FROM account_move_line
  WHERE move_id IN (
    SELECT MIN(id) AS id
    FROM account_move
    WHERE move_type IN ('liquidity')
    GROUP BY amount, journal_id, date, ref
    HAVING COUNT(id) > 1
  )
);
DELETE
FROM account_move
WHERE id IN (
  SELECT MIN(id) AS id
  FROM account_move
  WHERE move_type IN ('liquidity')
  GROUP BY amount, journal_id, date, ref
  HAVING COUNT(id) > 1
);
-- Segundo hacemos lo mismo pero con los asientos contables menos evidentes (sin referencia)
DELETE
FROM account_partial_reconcile
WHERE debit_move_id IN (
  SELECT id
  FROM account_move_line
  WHERE move_id IN (
    SELECT MIN(id) AS id
    FROM account_move
    WHERE move_type IN ('liquidity')
    GROUP BY amount, journal_id, date, partner_id
    HAVING COUNT(id) > 1
  )
)
   OR credit_move_id IN (
  SELECT id
  FROM account_move_line
  WHERE move_id IN (
    SELECT MIN(id) AS id
    FROM account_move
    WHERE move_type IN ('liquidity')
    GROUP BY amount, journal_id, date, partner_id
    HAVING COUNT(id) > 1
  )
);
DELETE
FROM account_move
WHERE id IN (
  SELECT MIN(id) AS id
  FROM account_move
  WHERE move_type IN ('liquidity')
  GROUP BY amount, journal_id, date, partner_id
  HAVING COUNT(id) > 1
);

-- Borramos los asientos de los pagos que hemos marcado para eliminar
-- 21548,22208,22678,23156,29892,21339,21448,21510,21603,22188,22202,22204,22536,22634,22682,22858,22859,22860,23035,23042,23205,29832,29863,29890
DELETE
FROM account_partial_reconcile
WHERE debit_move_id IN (
  SELECT id
  FROM account_move_line
  WHERE move_id IN (
    21548,22208,22678,23156,29892,21339,21448,21510,21603,22188,22202,22204,22536,22634,22682,22858,22859,22860,23035,23042,23205,29832,29863,29890
  )
)
   OR credit_move_id IN (
  SELECT id
  FROM account_move_line
  WHERE move_id IN (
    21548,22208,22678,23156,29892,21339,21448,21510,21603,22188,22202,22204,22536,22634,22682,22858,22859,22860,23035,23042,23205,29832,29863,29890
  )
);
DELETE
FROM account_move
WHERE id IN (
  21548,22208,22678,23156,29892,21339,21448,21510,21603,22188,22202,22204,22536,22634,22682,22858,22859,22860,23035,23042,23205,29832,29863,29890
);
-- Luego borramos los pagos que se hayan quedado pillados
DELETE
FROM account_payment
WHERE id IN (
  SELECT account_payment.id
  FROM account_payment
         LEFT JOIN account_move_line line ON line.payment_id = account_payment.id
  WHERE line.id IS NULL
    AND state NOT IN ('draft', 'cancelled')
);

-- Aquí deberíamos ejecutar el método fix_duplicate_payments y después eliminamos asientos

-- A mano comprobamos los extraños
SELECT MIN(id) AS id, amount, journal_id, date
FROM account_move
WHERE move_type IN ('liquidity')
GROUP BY amount, journal_id, date
HAVING COUNT(id) > 1;
SELECT string_agg(CAST(id AS VARCHAR), ',') ids, amount, date
FROM account_move
WHERE move_type IN ('liquidity')
GROUP BY amount, date
HAVING COUNT(id) > 1;