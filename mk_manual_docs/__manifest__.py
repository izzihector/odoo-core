# -*- coding: utf-8 -*-
{
    'name': "Documentos y Manuales",
    'summary': """
        Documentos y manuales de Melkart
    """,
    'description': """
        Este módulo tiene como objetivo subir los manuales para que los clientes sepa 
    """,
    "category": "Generic Modules",
    "website": "https://melkart.io",
    "author": "Melkart O&B",
    "license": "LGPL-3",
    'depends': ['chariots_core'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/mk_doc_doc_view.xml',
        'views/mk_doc_area_view.xml',
        'views/mk_doc_category_view.xml',
        'views/menu_item.xml',
        
    ],
    'demo': [],
    "qweb":[],
    'application': True,
    "installable": True,
}
