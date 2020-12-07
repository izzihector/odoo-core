# -*- coding: utf-8 -*-
{
    'name': "chariots_next_prev_button",
    'summary': """
        add next - previous button to popup x2many lines
        """,
    "description": """
    Add next - previous button to form popup for readonly one2many, many2many fields line.
""",
    'author': "Melkart O&B",
    'category': 'Dependency',
    'version': '1.0',
    # any module necessary for this one to work correctly
    'depends': ['web'],
    # always loaded
    'data': [
        'views/templates.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
    ],
    'active': False,
}
