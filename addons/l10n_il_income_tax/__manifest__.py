{
    'name': 'Israel - Income Tax',
    'version': '18.0.1.0.0',  # Updated to Odoo 18 format
    'category': 'Localization',
    'description': """
Israeli Income Tax Module
========================

This module provides:
* Income tax calculation for Israel
* Support for tax brackets and credit points
* Integration with payroll
* Income tax reporting with independent menu structure
    """,
    'author': 'Your Company',
    'website': 'https://www.yourcompany.com',
    'depends': [
        'hr_payroll',
        'l10n_il',
        # Don't depend on l10n_il_invoicing to keep modules separate
        # Don't depend on l10n_il_origen since it's not installable
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/income_tax_views.xml',
        'views/hr_employee_views.xml',
        'wizard/income_tax_report_wizard_views.xml',
        'data/income_tax_data.xml',
    ],
    'demo': [
        'demo/income_tax_demo.xml',
    ],
    'license': 'LGPL-3',
    'auto_install': False,
    'application': False,
    'installable': True,
}