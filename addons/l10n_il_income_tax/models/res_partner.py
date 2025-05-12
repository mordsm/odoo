# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class ResPartner(models.Model):
    _inherit = 'res.partner'
    
    # Israeli-specific fields
    l10n_il_id_number = fields.Char(
        string='Israeli ID Number',
        help='Israeli Identity Number (Teudat Zehut)'
    )
    
    l10n_il_tax_file_number = fields.Char(
        string='Tax File Number',
        help='Israeli Tax File Number (Tik Nikuim)'
    )
    
    l10n_il_income_tax_office_id = fields.Many2one(
        'l10n_il.tax.office',
        string='Income Tax Office',
        help='Tax office where the partner is registered'
    )
    
    l10n_il_tax_deduction_rate = fields.Float(
        string='Tax Deduction Rate (%)',
        help='Default income tax deduction rate for this partner',
        default=0.0
    )
    
    l10n_il_vat_exempt = fields.Boolean(
        string='VAT Exempt',
        help='Check if the partner is exempt from VAT'
    )


class IsraeliTaxOffice(models.Model):
    _name = 'l10n_il.tax.office'
    _description = 'Israeli Tax Office'
    
    name = fields.Char(string='Name', required=True)
    code = fields.Char(string='Code', required=True)
    city = fields.Char(string='City')
    address = fields.Char(string='Address')
    phone = fields.Char(string='Phone')
    email = fields.Char(string='Email')
    
    active = fields.Boolean(default=True)
    
    _sql_constraints = [
        ('code_uniq', 'unique(code)', 'Tax office code must be unique!'),
    ]