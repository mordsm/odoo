from odoo import api, fields, models, _


class AccountTax(models.Model):
    _inherit = 'account.tax'

    # Add Israeli tax report fields
    l10n_il_vat_category = fields.Selection([
        ('standard', 'Standard Rate (18%)'),
        ('reduced', 'Reduced Rate'),
        ('exempt', 'Exempt'),
        ('out_of_scope', 'Out of Scope'),
        ('import', 'Import VAT'),
        ('export', 'Export (0%)'),
    ], string='Israeli VAT Category', help="Category of VAT for Israeli reporting")
    
    l10n_il_report_line = fields.Selection([
        ('vat_sales', 'VAT on Sales'),
        ('vat_purchases', 'VAT on Purchases'),
        ('vat_import', 'VAT on Imports'),
        ('vat_export', 'Zero-rated Exports'),
        ('vat_exempt', 'Exempt Transactions'),
    ], string='Report Line', help="Specifies which line this tax will appear on Israeli VAT reports")


class AccountTaxGroup(models.Model):
    _inherit = 'account.tax.group'
    
    l10n_il_report_section = fields.Selection([
        ('input', 'Input VAT'),
        ('output', 'Output VAT'),
        ('exempt', 'Exempt'),
    ], string='Israeli Report Section')