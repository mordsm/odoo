from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class DepreciationSchedule(models.Model):
    _name = 'l10n_il.depreciation.schedule'
    _description = 'Israeli Depreciation Schedule'
    
    name = fields.Char(string='Reference', required=True, copy=False, readonly=True, default=lambda self: _('New'))
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id', string='Currency')
    fiscal_year = fields.Integer(string='Fiscal Year', required=True, default=lambda self: self._default_fiscal_year())
    date_from = fields.Date(string='From Date', required=True)
    date_to = fields.Date(string='To Date', required=True)
    
    depreciation_line_ids = fields.One2many('l10n_il.depreciation.schedule.line', 'schedule_id', string='Depreciation Lines')
    total_depreciation = fields.Monetary(string='Total Depreciation', compute='_compute_total', store=True, currency_field='currency_id')
    
    @api.model
    def _default_fiscal_year(self):
        return fields.Date.today().year
    
    @api.depends('depreciation_line_ids.depreciation_amount')
    def _compute_total(self):
        for record in self:
            record.total_depreciation = sum(record.depreciation_line_ids.mapped('depreciation_amount'))
    
    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for record in self:
            if record.date_from > record.date_to:
                raise ValidationError(_('Start date must be earlier than end date'))
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('l10n_il.depreciation.schedule') or _('New')
        return super().create(vals_list)

class DepreciationScheduleLine(models.Model):
    _name = 'l10n_il.depreciation.schedule.line'
    _description = 'Israeli Depreciation Schedule Line'
    
    schedule_id = fields.Many2one('l10n_il.depreciation.schedule', string='Schedule', required=True, ondelete='cascade')
    currency_id = fields.Many2one(related='schedule_id.currency_id', string='Currency')
    
    asset_id = fields.Many2one('account.asset', string='Asset', required=True)
    asset_category = fields.Selection([
        ('building', 'Building'),
        ('equipment', 'Equipment'),
        ('vehicle', 'Vehicle'),
        ('computer', 'Computer'),
        ('furniture', 'Furniture'),
        ('software', 'Software'),
        ('other', 'Other')
    ], string='Asset Category')
    
    acquisition_date = fields.Date(string='Acquisition Date')
    acquisition_value = fields.Monetary(string='Acquisition Value', currency_field='currency_id')
    depreciation_rate = fields.Float(string='Depreciation Rate (%)')
    depreciation_amount = fields.Monetary(string='Depreciation Amount', currency_field='currency_id')
    accumulated_depreciation = fields.Monetary(string='Accumulated Depreciation', currency_field='currency_id')
    net_book_value = fields.Monetary(string='Net Book Value', compute='_compute_net_book_value', store=True, currency_field='currency_id')
    
    @api.depends('acquisition_value', 'accumulated_depreciation')
    def _compute_net_book_value(self):
        for record in self:
            record.net_book_value = record.acquisition_value - record.accumulated_depreciation