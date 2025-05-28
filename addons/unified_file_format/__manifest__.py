{
    'name': 'Unified File Format Israel',
    'version': '18.0.1.0.0',
    'depends': ['base', 'web'],
    'data': [
        'security/ir.model.access.csv',
        'views/file_format_views.xml',
        'views/financial_transaction_views.xml',  # ADD this line
        'views/menu_views.xml',
    ],
    'installable': True,
    'application': True,
}