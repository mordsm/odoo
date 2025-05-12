from odoo import api, fields, models, _
from odoo.exceptions import UserError
from datetime import datetime

class GenerateTaxReportsWizard(models.TransientModel):
    _name = 'l10n_il.generate.tax.reports.wizard'
    _description = 'Generate Israeli Tax Reports Wizard'
    
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    fiscal_year = fields.Integer(string='Fiscal Year', required=True, default=lambda self: datetime.now().year)
    report_type = fields.Selection([
        ('corporate_tax', 'Corporate Tax Return'),
        ('depreciation', 'Depreciation Schedule'),
        ('both', 'Both Reports')
    ], string='Report Type', default='both', required=True)
    
    date_from = fields.Date(string='From Date', required=True, default=lambda self: fields.Date.from_string(f"{datetime.now().year}-01-01"))
    date_to = fields.Date(string='To Date', required=True, default=lambda self: fields.Date.from_string(f"{datetime.now().year}-12-31"))
    
    def action_generate_reports(self):
        self.ensure_one()
        
        if self.report_type in ('corporate_tax', 'both'):
            # Generate Corporate Tax Return
            corporate_tax = self.env['l10n_il.corporate.tax.return'].create({
                'company_id': self.company_id.id,
                'fiscal_year': self.fiscal_year,
                # Add logic to pre-fill data from accounting entries
            })
            
        if self.report_type in ('depreciation', 'both'):
            # Generate Depreciation Schedule
            depreciation_schedule = self.env['l10n_il.depreciation.schedule'].create({
                'company_id': self.company_id.id,
                'fiscal_year': self.fiscal_year,
                'date_from': self.date_from,
                'date_to': self.date_to,
                # Add logic to pre-fill data from assets
            })
            
            # Fetch all assets for the company
            assets = self.env['account.asset'].search([
                ('company_id', '=', self.company_id.id),
                ('acquisition_date', '<=', self.date_to),
                ('state', 'in', ['open', 'paused']),
            ])
            
            # Create depreciation lines
            depreciation_lines = []
            for asset in assets:
                # This is a simplified calculation, actual implementation would use asset data
                vals = {
                    'schedule_id': depreciation_schedule.id,
                    'asset_id': asset.id,
                    'asset_category': 'other',  # Map from asset category if available
                    'acquisition_date': asset.acquisition_date,
                    'acquisition_value': asset.original_value,
                    'depreciation_rate': asset.method_progress_factor * 100 if asset.method == 'degressive' else 100 / asset.method_number,
                    'depreciation_amount': self._calculate_yearly_depreciation(asset),
                    'accumulated_depreciation': self._calculate_accumulated_depreciation(asset, self.date_to),
                }
                depreciation_lines.append(vals)
                
            if depreciation_lines:
                self.env['l10n_il.depreciation.schedule.line'].create(depreciation_lines)
        
        # Show appropriate view based on report type
        if self.report_type == 'corporate_tax':
            return {
                'name': _('Corporate Tax Return'),
                'view_mode': 'form',
                'res_model': 'l10n_il.corporate.tax.return',
                'res_id': corporate_tax.id,
                'type': 'ir.actions.act_window',
            }
        elif self.report_type == 'depreciation':
            return {
                'name': _('Depreciation Schedule'),
                'view_mode': 'form',
                'res_model': 'l10n_il.depreciation.schedule',
                'res_id': depreciation_schedule.id,
                'type': 'ir.actions.act_window',
            }
        else:
            # If both, show a notification and go to menu
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Reports Generated'),
                    'message': _('Corporate Tax Return and Depreciation Schedule have been generated successfully.'),
                    'type': 'success',
                    'sticky': False,
                    'next': {
                        'type': 'ir.actions.act_window_close',
                    },
                }
            }
    
    def _calculate_yearly_depreciation(self, asset):
        """Calculate yearly depreciation amount for an asset"""
        # This is a simplified calculation
        if asset.method == 'linear':
            return asset.original_value / asset.method_number
        elif asset.method == 'degressive':
            return asset.original_value * asset.method_progress_factor
        return 0.0
    
    def _calculate_accumulated_depreciation(self, asset, date):
        """Calculate accumulated depreciation for an asset up to given date"""
        # This is a simplified calculation
        # In a real implementation, you would need to consider:
        # - Prorated amount for the first and last years
        # - Actual depreciation moves that have been posted
        # - Changes in depreciation method or value over time
        
        # For now, just return the total depreciation posted
        return sum(asset.depreciation_move_ids.filtered(
            lambda m: m.date <= date and m.state == 'posted'
        ).mapped('amount_total'))

# Wizard action
class GenerateTaxReportsWizardAction(models.Model):
    _name = 'l10n_il.generate.tax.reports.wizard.action'
    _description = 'Action for Generate Tax Reports Wizard'
    
    @api.model
    def action_generate_tax_reports_wizard(self):
        return {
            'name': _('Generate Tax Reports'),
            'type': 'ir.actions.act_window',
            'res_model': 'l10n_il.generate.tax.reports.wizard',
            'view_mode': 'form',
            'target': 'new',
        }

# Action reference
action_generate_tax_reports_wizard = """
<record id="action_generate_tax_reports_wizard" model="ir.actions.act_window">
    <field name="name">Generate Tax Reports</field>
    <field name="res_model">l10n_il.generate.tax.reports.wizard</field>
    <field name="view_mode">form</field>
    <field name="target">new</field>
</record>
"""