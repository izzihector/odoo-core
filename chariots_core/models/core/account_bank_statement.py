# -*- coding: utf-8 -*-


import base64
import datetime
from dateutil import parser
import logging
import pathlib
import time
from os import listdir
from odoo.exceptions import UserError, ValidationError

from odoo import models, fields, api
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT

import paramiko
from paramiko.common import xffffffff

from ...tools.ftp import ChariotsFTP


class AccountBankStatement(models.TransientModel):
    _inherit = "account.bank.statement.import"

    def _files_process(self, files, all, up_file):
        for file in files:
            filename = file.split('/')[-1]
            with open(file, 'rb') as f:
                contents_b64 = f.read()
                contents_b64 = base64.b64encode(contents_b64)
                self.env['ir.attachment'].sudo().create({
                    'name': filename,
                    'res_name': filename,
                    'folder_id': self.env.ref('chariots_core.folder_sabadell').id,
                    'type': 'binary',
                    'datas': contents_b64
                })
            if up_file:
                with open(file, 'r', encoding="iso-8859-1") as f:
                    contents = f.read()
                accounts = self._parse_files(contents)
                self._execute_cron(accounts)

    def import_local_files(self):
        path = pathlib.Path(__file__).parent.parent.parent.absolute()
        local_route = "{}/{}".format(path, "files")
        for file in listdir(local_route):
            self._files_process(["{}/{}".format(local_route, file)], all=True, up_file=True)

    def _ir_log(self, message, func, line=1):
        IrLogging = self.env['ir.logging']
        IrLogging.sudo().create({
            'name': 'account_bank_statement_log',
            'type': 'server',
            'dbname': self.env.cr.dbname,
            'level': 'DEBUG',
            'message': message,
            'path': "",
            'func': func,
            'line': line
        })

    @api.model
    def cron_get_transactions(self, all=False, local=False):
        if local:
            return self.import_local_files()
        ir_config = self.env['ir.config_parameter']
        domain = ir_config.get_param('Ftp_Sabadell.domain')
        username = ir_config.get_param('Ftp_Sabadell.username')
        key_file = ir_config.get_param('Ftp_Sabadell.key')
        local_path = ir_config.get_param('Ftp_Sabadell.path')
        last_import_date = ir_config.get_param('Ftp_Sabadell.last_import')
        filesize = ir_config.get_param('Ftp_Sabadell.filesize')
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        key = paramiko.RSAKey.from_private_key_file(key_file)
        ssh.connect(domain, username=username, pkey=key)
        sftp = ssh.open_sftp()
        directories = sftp.listdir_iter('/N43')
        today = time.strftime('%Y-%m-%d')
        ir_config.set_param('Ftp_Sabadell.last_import', today)
        for dir in directories:
            size = dir.st_size
            remote_route = "/N43/{}".format(dir.filename)
            local_route = "{}/{}".format(local_path, dir.filename)
            if (dir.st_mtime is None) or (dir.st_mtime == xffffffff):
                datestr = '(unknown date)'
            else:
                datestr = time.strftime('%Y-%m-%d', time.localtime(dir.st_mtime))
            if datestr <= last_import_date:
                self._ir_log(
                    message="No se importa el fichero por que la fecha {} es menor que {} \n {}".format(
                        datestr,
                        last_import_date,
                        str(dir)
                    ),
                    func="cron_get_transactions.ko",
                    line=89,
                )
                continue
            if filesize == size:
                self._ir_log(
                    message="No se importa el fichero por que la tamaño {} es igual que {} \n {}".format(
                        filesize,
                        size,
                        str(dir)
                    ),
                    func="cron_get_transactions",
                    line=100,
                )
                continue
            search_sabadell_file = self.env['account.bank.statement'].search([
                ('create_date', '>=', "{} 00:00:00".format(datestr)),
                ('create_date', '<=', "{} 23:59:59".format(datestr)),
                ('journal_id.bank_id.bic', '=', 'BSABESBBXXX')
            ])
            if not search_sabadell_file:
                sftp.get(remote_route, local_route)
                self._files_process([local_route], all, True)
                ir_config.set_param('Ftp_Sabadell.size', size)
                self._ir_log(
                    message="Se ha importado \n {}".format(
                        str(dir)
                    ),
                    func="cron_get_transactions.ok",
                    line=117,
                )
            else:
                self._ir_log(
                    message="No se importa el fichero por que hay archivos en esa misma fecha {} \n {}".format(
                        str("{} 00:00:00".format(datestr)),
                        str(dir),
                    ),
                    func="cron_get_transactions.ko",
                    line=115,
                )
            self.env.cr.commit()
        ssh.close()
        return True

    def _process_record_88(self, st_data, line):
        """88 - Registro de fin de archivo"""
        st_data['num_registros'] = int(line[20:26])
        return st_data

    @api.model
    def _parse_files(self, contents):
        acc_journ_obj = self.env['account.journal']
        res_partner_bank_obj = self.env['res.partner.bank']
        accounts = {}
        account = ''
        if contents.find("\n") > -1:
            lines = contents.split("\n")
        else:
            lines = []
            size = len(contents)
            mini = 0
            for i in range(int(size / 80)):
                maxi = 80 * (i + 1)
                lines.append(contents[mini:maxi])
                mini = maxi
        for line in lines:
            bien = False
            rest = False
            min_indice = 80
            for inicio in ['2301', '2302', '2303', '2304', '2305', '2306', '11', '22', '24', '33', '88']:
                indice = line.find(inicio)
                if indice == 0:
                    bien = True
                elif indice < min_indice and indice > -1:
                    min_indice = indice
            if not bien and min_indice != 80:
                rest = line[0:min_indice]
                line = line[min_indice:]
            if line[0:2] == '11':
                account = line[10:20]
                if account not in accounts:
                    # Buscamos la cuenta bancaria
                    res_partner_banks_search = res_partner_bank_obj.search([
                        ('acc_number', '=like', "%{}".format(account))
                    ], limit=1)
                    # Si ha encontrado la cuenta bancaria va a ir a buscar el diario correspondiente
                    if res_partner_banks_search:
                        acc_search = acc_journ_obj.search([('bank_account_id', '=', res_partner_banks_search.id)])
                        accounts[account] = {
                            'lines': '',
                            'journal_id': acc_search.id if acc_search else False
                        }
                        accounts[account]['lines'] += line + "\n"
            else:
                # Si ha encontrado tanto la cuenta bancaria en Odoo añadimos las lineas
                if account in accounts:
                    if rest:
                        accounts[account]['lines'] = accounts[account]['lines'][:-1] + rest + "\n"
                    accounts[account]['lines'] += line + "\n"
        return accounts

    @api.model
    def _execute_cron(self, accounts):
        acc_bank_statement_obj = self.env['account.bank.statement']
        acc_bank_statement_line_obj = self.env['account.bank.statement.line']
        res_partner_bank_obj = self.env['res.partner.bank']
        for acc_key, acc_object in accounts.items():
            journal_id = acc_object['journal_id']
            # Si la cuenta actual no tiene un diario asociado no podemos crear las transacciones ya que nos lo pide Odoo de forma obligatoria
            if not journal_id:
                logging.error('La cuenta bancaria termina en ' + acc_key)
                continue
            lines = acc_object['lines']
            # En esta parte transformamos y que nos devuelvan las lineas en el formato correcto
            result = self._parse(lines)
            context = dict(self._context or {})
            context.update({'journal_id': journal_id})
            res_parse_file = self.with_context(context)._parse_file_ftp(result)
            # Si no hemos conseguido que se transforme correctamente no creamos ninguna transaccion en Odoo
            if not res_parse_file:
                continue
            lines_transactions = res_parse_file['transactions']
            balance_start = res_parse_file['balance_start']
            balance_end_real = res_parse_file['balance_end_real']
            date = res_parse_file['date']
            new_acc_bank_state = acc_bank_statement_obj.create({
                'balance_start': balance_start,
                'balance_end_real': balance_end_real,
                'journal_id': journal_id,
                'name': str(date),
                'date': str(date)
            })
            new_acc_bank_state.write({
                'name': datetime.datetime.strptime(
                    str(new_acc_bank_state.date),
                    DEFAULT_SERVER_DATE_FORMAT).strftime(
                    '%d/%m/%Y'
                )
            })
            # Si ha dado fallo al crear la transaccion sin lineas no creamos lineas de transaccion en Odoo
            if not new_acc_bank_state:
                continue
            # Si ha todo ha ido bien recorremos las lineas que nos han devuelto
            for l in lines_transactions:
                line_transaction = l
                # Convertimos el campo notas en cadena ya que en Odoo lo guarda de esta forma
                note = line_transaction['note']

                # Buscamos la empresa para esa linea
                if note['conceptos'].get('02'):
                    bank_account_number = str(note['conceptos']['02'])

                    bank_account_number = bank_account_number.replace('(', '')
                    bank_account_number = bank_account_number.replace(')', '')
                    bank_account_number = bank_account_number.split(',')

                    bank_account_number = bank_account_number[0]
                    bank_account_number = bank_account_number.replace("'", '')
                    if bank_account_number:
                        bank_account_number
                        res_partner_banks_search = res_partner_bank_obj.search([
                            ('sanitized_acc_number', '=', '{}'.format(bank_account_number))
                        ], limit=1)

                        if res_partner_banks_search:
                            line_transaction['partner_id'] = res_partner_banks_search.partner_id.id
                value_note, value_name, transfer_intern, value_pay = self.get_vals_formatted(line_transaction['note'],
                                                                                             name=line_transaction[
                                                                                                 'name'])
                line_transaction['note'] = value_note
                if transfer_intern:
                    line_transaction['name'] = value_name
                    line_transaction['account_payment_id'] = value_pay.id if value_pay else False
                    if value_pay:
                        if value_pay.partner_id:
                            line_transaction['partner_id'] = value_pay.partner_id.id

                # Asociamos la linea a la transaccion que hemos creado anteriormente
                line_transaction.update({'statement_id': new_acc_bank_state.id})
                new_acc_bank_state_line = acc_bank_statement_line_obj.create(line_transaction)
                # Si ha dado error al crear la linea nueva solo mostramos un logging para saber que línea es. Esto es solo pura información para saber si la hemos generado mal.
                if not new_acc_bank_state_line:
                    logging.error('no se ha creado correctamente la linea: ' + line_transaction)

    @api.model
    def _parse_file_ftp(self, data_file):
        context = dict(self._context or {})
        # Recogemos el diario
        journal = self.env['account.journal'].browse(
            context.get('journal_id')
        )
        transactions = []
        date = datetime.date.today()
        for group in data_file:
            for line in group['lines']:
                if '01' in line['conceptos']:
                    conceptos = "{}{}".format(
                        line['conceptos']['01'][0],
                        line['conceptos']['01'][1]
                    ).replace('CORE', 'CORE ')
                else:
                    conceptos = "Sin Concepto¿?"
                # Se va guardando la informacion en un diccionario
                date = fields.Date.to_string(line[journal.n43_date_type or 'fecha_valor'])
                vals_line = {
                    'date': date,
                    'name': conceptos,
                    'ref': self._get_ref(line),
                    'amount': line['importe'],
                    'note': line,
                }
                c = line['conceptos']
                if c.get('01'):
                    vals_line['partner_name'] = c['01'][0] + c['01'][1]
                if not vals_line['name']:  # pragma: no cover
                    vals_line['name'] = vals_line['ref']
                transactions.append(vals_line)

        # Estos son los valores de la transaccion: Lineas, Saldo de inicio y saldo final en Odoo
        vals_bank_statement = {
            'transactions': transactions,
            'date': date,
            'balance_start': data_file and data_file[0]['saldo_ini'] or 0.0,
            'balance_end_real': data_file and data_file[-1]['saldo_fin'] or 0.0,
        }
        return vals_bank_statement

    def get_vals_formatted(self, vals, name='', transfer_intern=False, payment_id=False):
        text = ''
        for key, val in vals.items():
            if key == 'of_origen':
                key = 'Oficina de Origen'
            elif key == 'fecha_oper':
                key = 'Fecha de Operación'
            elif key == 'fecha_valor':
                key = 'Fecha Efectiva'
            elif key == 'concepto_c':
                continue
            elif key == 'concepto_p':
                continue
            elif key == 'importe':
                continue
            elif key == 'referencia1':
                continue
            elif key == 'referencia2':
                continue

            if isinstance(val, dict):
                value_text, value_name, value_transfer_intern, value_pay = self.get_vals_formatted(
                    val,
                    name=name,
                    transfer_intern=transfer_intern
                )
                name = value_name
                transfer_intern = value_transfer_intern
                payment_id = value_pay
                text += value_text + '\n'
            elif isinstance(val, datetime.datetime):
                val = datetime.datetime.strptime(str(val.date()), DEFAULT_SERVER_DATE_FORMAT).strftime('%d/%m/%Y')
                text += ' ' + val + ' '
            elif isinstance(val, list) or isinstance(val, tuple):
                if key == '01':
                    val_text = str(val[0]) + str(val[1])
                    if val_text.startswith('TRANSFERENCIA', 0, 13) or val_text.startswith('TRANSFER', 0, 8):
                        # if self.env.ref('base.main_company').name in val_text:
                        transfer_intern = True
                if key == '03':
                    nam_pay = str(val[0])
                    nam_pay = nam_pay.split(' ')
                    pay_id = ''
                    if len(nam_pay) >= 4:
                        pay_id = nam_pay[2]
                    if pay_id and transfer_intern:
                        try:
                            payment = self.env['account.payment'].search([('id', '=', int(pay_id))])
                            if payment:
                                if payment.payment_type == 'transfer':
                                    name = 'Transferencia a {} de {}'.format(
                                        payment.destination_journal_id.name,
                                        payment.journal_id.name
                                    )
                                payment_id = payment
                        except:
                            payment_id = False
                text += " ".join(val)
            else:
                val = str(val)
                val = val.replace('(', '')
                val = val.replace(')', '')
                val = val.replace("'", '')
                text += ' ' + val
        return text, name, transfer_intern, payment_id


class AccountBankStatementLine(models.Model):
    _inherit = "account.bank.statement.line"

    _order = "date desc"

    account_payment_id = fields.Many2one(comodel_name='account.payment', string='Pago')
    auto_reconciliation = fields.Boolean(string='Auto Conciliado?')

    def cron_auto_reconciliation(self):
        st_lines = self.env[self._name].search(
            [('account_payment_id', '!=', False), ('journal_id', '!=', False), ('journal_entry_ids', '=', False)])
        model_reconcile = self.env['account.reconcile.model']
        data = {}
        if st_lines:
            for line in st_lines:
                if line.account_payment_id and not line.journal_entry_ids:
                    payment = line.account_payment_id
                    result = ''
                    if payment.partner_type == 'supplier' and payment.partner_id and payment.move_line_ids and payment.state != 'reconciled':
                        aml_ids = payment.move_line_ids
                        aml_ids = aml_ids.filtered(lambda x: x.account_id.internal_type == 'liquidity')
                        if aml_ids:
                            if line.move_name:
                                line.write({'move_name': ''})
                            res = line.process_reconciliation(payment_aml_rec=aml_ids)
                            if res:
                                line.write({'auto_reconciliation': True})
                                if not line.journal_id.id in data:
                                    data[line.journal_id.id] = {
                                        'name': line.journal_id.name,
                                        'qty': 1,
                                        'line_ids': [{
                                            'date': datetime.datetime.strptime(
                                                str(line.date),
                                                DEFAULT_SERVER_DATE_FORMAT).strftime(
                                                '%d/%m/%Y'
                                            ),
                                            'amount': line.amount,
                                            'partner_id': line.partner_id.name,
                                            'name': line.name,
                                            'payment': line.account_payment_id.name
                                        }]
                                    }
                                else:
                                    data[line.journal_id.id]['qty'] += 1
                                    if data['line_ids']:
                                        data[line.journal_id.id]['line_ids'] = data[line.journal_id.id][
                                            'line_ids'].append({
                                            'date': datetime.datetime.strptime(
                                                str(line.date),
                                                DEFAULT_SERVER_DATE_FORMAT).strftime(
                                                '%d/%m/%Y'
                                            ),
                                            'amount': line.amount,
                                            'partner_id': line.partner_id.name,
                                            'name': line.name,
                                            'payment': line.account_payment_id.name
                                        })
        if not data:
            return False
        content = ''
        for dat in data:
            content += '<p>{} Cantidad: {}</p> <br>'.format(data[dat]['name'], str(data[dat]['qty']))
            line_ids = data[dat]['line_ids']
            if line_ids:
                t_body = """"""
                for line in line_ids:
                    t_body += """
                        <tr>
                            <td style="height:40px;border:1px solid black;border-collapse:collapse;text-align:center;">{name}</td>
                            <td style="height:40px;border:1px solid black;border-collapse:collapse;text-align:center;">{date}</td>
                            <td style="height:40px;border:1px solid black;border-collapse:collapse;text-align:center;">{amount} {symbol}</td>
                            <td style="height:40px;border:1px solid black;border-collapse:collapse;text-align:center;">{partner_id}</td>
                            <td style="height:40px;border:1px solid black;border-collapse:collapse;text-align:center;">{payment}</td>
                        </tr>
                    """.format(
                        date=line['date'],
                        amount=line['amount'],
                        partner_id=line['partner_id'],
                        name=line['name'],
                        payment=line['payment'],
                        symbol=self.env.user.company_id.currency_id.symbol
                    )

                content += """
                    <table style="width:80%;border:1px solid black;border-collapse:collapse;">
                        <tr>
                            <th style="border:1px solid black;border-collapse:collapse;text-align:center;">Etiqueta</th>
                            <th style="border:1px solid black;border-collapse:collapse;text-align:center;">Fecha</th>
                            <th style="border:1px solid black;border-collapse:collapse;text-align:center;">Importe</th>
                            <th style="border:1px solid black;border-collapse:collapse;text-align:center;">Destinatario</th>
                            <th style="border:1px solid black;border-collapse:collapse;text-align:center;">Pago</th>
                        </tr>
                        {}
                    </table>
                    <br/>
                """.format(t_body)

        message = "Transferencias auto conciliadas {}".format(content)
        self.env.ref('chariots_core.st_line_conc_auto_channel').message_post(
            body=message, author_id=2,
            message_type="comment", subtype="mail.mt_comment"
        )
        return True

    def cron_auto_del_reconciliation(self):
        st_lines = self.env[self._name].search([('auto_reconciliation', '=', True)])
        if st_lines:
            for line in st_lines:
                if line.account_payment_id:
                    line.button_cancel_reconciliation()
                    line.write({'auto_reconciliation': False})
        return True

    def cron_assignate_payment(self):
        st_lines = self.env[self._name].search([
            ('account_payment_id', '=', False),
            ('journal_id', '!=', False),
            ('journal_entry_ids', '=', False),
            ('name', 'like', "{}%".format('TRANSF')),
            ('note', '!=', False)
        ])
        acc_payment_obj = self.env['account.payment']
        if st_lines:
            st_lines = st_lines.filtered(lambda x: x.name.startswith('TRANSF', 0, 6))
            if st_lines:
                for line in st_lines:
                    payment_note = line.note
                    payment_id = line.note
                    payment_assigned = False
                    payment_id = payment_id.split('REF')
                    if len(payment_id) > 1:
                        payment_id = payment_id[1].split(' ')
                        try:
                            payment_id = int(payment_id[2])
                            payment_id = acc_payment_obj.search([('id', '=', payment_id)])
                            if payment_id:
                                line.write({'account_payment_id': payment_id.id})
                                if payment_id.partner_id and not line.partner_id:
                                    line.write({'partner_id': payment_id.partner_id.id})
                                payment_assigned = True
                        except Exception as error:
                            if not payment_assigned:
                                payment_note = payment_note.split('OBSERVACIONES')
                                logging.error(payment_note)
                                if len(payment_note) > 1:
                                    payment_note = payment_note[0]
                                    if len(payment_note) > 18:
                                        payment_note = payment_note[-18:]
                                        payment_note = acc_payment_obj.search([('name', '=', payment_note)])
                                        if payment_note:
                                            line.write({'account_payment_id': payment_note.id})
                                            if payment_note.partner_id and not line.partner_id:
                                                line.write({'partner_id': payment_note.partner_id.id})
                            pass

        return True


class AccBankStatement(models.Model):
    _inherit = "account.bank.statement"

    @api.multi
    def extract_cancel(self):
        for ext in self:
            if ext.line_ids:
                ext.line_ids.button_cancel_reconciliation()
                ext.unlink()
            else:
                ext.unlink()
