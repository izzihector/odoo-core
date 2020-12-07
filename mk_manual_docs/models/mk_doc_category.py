# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo import SUPERUSER_ID

import logging
from lxml import etree


class MkDocCategory(models.Model):

    _name = "mk.doc.category"
    _description = "Categoría del Documento"

    name = fields.Char(string='Nombre')
    active = fields.Boolean(string='Activo', default=True)

    @api.model
    def fields_view_get(self, view_id=None, view_type='form',
                        toolbar=False, submenu=False):

        res = super(MkDocCategory, self).fields_view_get(
            view_id=view_id, view_type=view_type,
            toolbar=toolbar, submenu=submenu)

        if view_type != 'search' and self.env.uid != SUPERUSER_ID:
            # Comprobamos si el usuario actual pertenece al grupo de usuarios de editoe si no lo es no podra ni editar ni crear documentos
            has_my_group = self.env.user.has_group('mk_manual_docs.group_editor_chariots_documentos')
            if not has_my_group:
                root = etree.fromstring(res['arch'])
                root.set('create', 'false')
                root.set('edit', 'false')
                res['arch'] = etree.tostring(root)

        return res