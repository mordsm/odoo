# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class ResCompany(models.Model):
    _inherit = 'res.company'
    
    # Israeli-specific company fields
    l10n_il_company_id = fields.Char(
        string='Israeli Company ID',
        help='Company ID number (תעודת רישום חברה)'
    )
    
    l10n_il_tax_withholding_number = fields.Char(
        string='Tax Withholding Number',
        help='Tax withholding file number (תיק ניכויים)'
    )
    
    l10n_il_income_tax_office_id = fields.Many2one(
        'l10n_il.tax.office',
        string='Income Tax Office',
        help='Tax office where the company is registered'
    )
    
    l10n_il_tax_deduction_certificate = fields.Binary(
        string='Tax Deduction Certificate',
        attachment=True,
        help='Scanned copy of tax deduction certificate (אישור ניכוי מס במקור)'
    )
    
    l10n_il_tax_deduction_cert_filename = fields.Char(
        string='Tax Deduction Certificate Filename'
    )
    
    l10n_il_social_security_number = fields.Char(
        string='Social Security Number',
        help='National Insurance Institute employer number (מספר תיק מעסיק בביטוח לאומי)'
    )
    
    l10n_il_tax_year_start = fields.Selection(
        selection=[
            ('1', 'January'),
            ('4', 'April'),
            ('10', 'October')
        ],
        string='Tax Year Start',
        default='1',
        help='Month when the tax year starts'
    )
    
    @api.onchange('country_id')
    def _onchange_country_id(self):
        """Set default values when country is Israel"""
        if self.country_id and self.country_id.code == 'IL':
            self.l10n_il_tax_year_start = '1'  # January is default in Israel