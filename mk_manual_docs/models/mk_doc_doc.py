# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo import SUPERUSER_ID

import logging
from lxml import etree



class MkDocDoc(models.Model):

    _name = "mk.doc.doc"
    _description = "Documento"

    name = fields.Char(string='Título')
    subtitle = fields.Char(string='Subtítulo')
    description = fields.Html(string='Descripción')
    order = fields.Float(string='Orden')
    parent_document_id = fields.Many2one(
        comodel_name="mk.doc.doc",
        string="Documento Padre"
    ) 
    mk_doc_area_id = fields.Many2one(
        comodel_name="mk.doc.area",
        string="Área"
    )
    mk_doc_category_id = fields.Many2one(
        comodel_name="mk.doc.category",
        string="Categoría"
    )
    attachment_ids = fields.Many2many(
        comodel_name="ir.attachment",
        string="Adjuntos"
    )
    
    @api.model
    def fields_view_get(self, view_id=None, view_type='form',
                        toolbar=False, submenu=False):

        res = super(MkDocDoc, self).fields_view_get(
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