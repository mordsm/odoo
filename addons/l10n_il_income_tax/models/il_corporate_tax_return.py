from odoo import api, fields, models, _
from odoo.exceptions import UserError

class CorporateTaxReturn(models.Model):
    _name = 'l10n_il.corporate.tax.return'
    _description = 'Israeli Corporate Tax Return'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    name = fields.Char(string='Reference', required=True, copy=False, readonly=True, default=lambda self: _('New'))
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id', string='Currency')
    fiscal_year = fields.Integer(string='Fiscal Year', required=True, default=lambda self: self._default_fiscal_year())
    submission_date = fields.Date(string='Submission Date')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string='Status', default='draft', tracking=True)
    
    # Corporate tax specific fields
    income_from_sales = fields.Monetary(string='Income from Sales', currency_field='currency_id')
    income_from_services = fields.Monetary(string='Income from Services', currency_field='currency_id')
    other_income = fields.Monetary(string='Other Income', currency_field='currency_id')
    total_income = fields.Monetary(string='Total Income', compute='_compute_totals', store=True, currency_field='currency_id')
    
    cost_of_goods_sold = fields.Monetary(string='Cost of Goods Sold', currency_field='currency_id')
    operational_expenses = fields.Monetary(string='Operational Expenses', currency_field='currency_id')
    salary_expenses = fields.Monetary(string='Salary Expenses', currency_field='currency_id')
    depreciation_expenses = fields.Monetary(string='Depreciation Expenses', currency_field='currency_id')
    finance_expenses = fields.Monetary(string='Finance Expenses', currency_field='currency_id')
    other_expenses = fields.Monetary(string='Other Expenses', currency_field='currency_id')
    total_expenses = fields.Monetary(string='Total Expenses', compute='_compute_totals', store=True, currency_field='currency_id')
    
    net_profit_before_tax = fields.Monetary(string='Net Profit Before Tax', compute='_compute_totals', store=True, currency_field='currency_id')
    tax_amount = fields.Monetary(string='Tax Amount', compute='_compute_tax_amount', store=True, currency_field='currency_id')
    
    @api.model
    def _default_fiscal_year(self):
        return fields.Date.today().year
    
    @api.depends('income_from_sales', 'income_from_services', 'other_income',
                'cost_of_goods_sold', 'operational_expenses', 'salary_expenses',
                'depreciation_expenses', 'finance_expenses', 'other_expenses')
    def _compute_totals(self):
        for record in self:
            record.total_income = sum([
                record.income_from_sales or 0.0,
                record.income_from_services or 0.0,
                record.other_income or 0.0
            ])
            
            record.total_expenses = sum([
                record.cost_of_goods_sold or 0.0,
                record.operational_expenses or 0.0,
                record.salary_expenses or 0.0,
                record.depreciation_expenses or 0.0,
                record.finance_expenses or 0.0,
                record.other_expenses or 0.0
            ])
            
            record.net_profit_before_tax = record.total_income - record.total_expenses
    
    @api.depends('net_profit_before_tax')
    def _compute_tax_amount(self):
        for record in self:
            # Simplified corporate tax calculation
            # Replace with actual Israeli tax calculation
            if record.net_profit_before_tax > 0:
                record.tax_amount = record.net_profit_before_tax * 0.23  # 23% is the Israeli corporate tax rate
            else:
                record.tax_amount = 0.0
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('l10n_il.corporate.tax.return') or _('New')
        return super().create(vals_list)
    
    def action_submit(self):
        self.write({'state': 'submitted', 'submission_date': fields.Date.today()})
    
    def action_approve(self):
        self.write({'state': 'approved'})
    
    def action_reject(self):
        self.write({'state': 'rejected'})
    
    def action_reset_to_draft(self):
        self.write({'state': 'draft'})