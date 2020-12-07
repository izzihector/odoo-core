-- Detectar Repetidos Binarios
SELECT COUNT(id), res_id, res_model
FROM ir_attachment
WHERE res_model = 'account.invoice' AND type != 'url'
GROUP BY res_model, res_id
HAVING COUNT(id) > 1;
-- Detectar Repetidos URL
SELECT COUNT(id), res_id, res_model
FROM ir_attachment
WHERE res_model = 'account.invoice' AND type = 'url'
GROUP BY res_model, res_id
HAVING COUNT(id) > 1;
-- Eliminarlos
DELETE FROM ir_attachment
WHERE id IN (
  SELECT MAX(id)
  FROM ir_attachment
  WHERE res_model = 'account.invoice' AND type = 'url'
  GROUP BY res_model, res_id
  HAVING COUNT(id) > 1
);
