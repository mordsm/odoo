{
    'name': 'Israel - VAT Reporting',
    'version': '18.0.1.0.0',  # Adjust version based on your Odoo version
    'category': 'Accounting/Localizations/Reporting',
    'description': """
Israeli Localization - VAT Reporting
====================================

This module adds VAT reporting features for Israeli businesses without requiring the full accounting module.
Includes:
* VAT report (PCN 874)
* Tax codes for Israeli reporting
    """,
    'author': 'Transforo',
    'website': 'https://www.transforo.com',
    'depends': [
        'account',  # Core invoicing module
        'base',     # Base module
    ],
   

    'data': [
    'security/ir.model.access.csv',
    'menu_fix.xml',      
    'income_tax_menus.xml',  # Add this line
    'views/income_tax_views.xml',
    'views/hr_employee_views.xml',
    'wizard/income_tax_report_wizard_views.xml',
    'data/income_tax_data.xml',
],

    'demo': [],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}