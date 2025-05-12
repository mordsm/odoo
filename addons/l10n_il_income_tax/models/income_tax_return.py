# -*- coding: utf-8 -*-

from datetime import date
from dateutil.relativedelta import relativedelta
import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


_logger = logging.getLogger(__name__)


class IncomeTaxReturn(models.Model):
    _name = 'l10n_il.income.tax.return'
    _description = 'Israeli Income Tax Return'
    _order = 'date desc, id desc'
    
    name = fields.Char(string='Reference', required=True, copy=False, 
                       readonly=True, default=lambda self: _('New'))
    date = fields.Date(string='Date', required=True, default=fields.Date.today)
    employee_id = fields.Many2one('hr.employee', string='Employee', required=True)
    year = fields.Integer(string='Tax Year', required=True, default=lambda self: fields.Date.today().year)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='draft', tracking=True)
    
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id')
    
    # Annual income details
    annual_salary = fields.Monetary(string='Annual Salary', currency_field='currency_id')
    annual_bonus = fields.Monetary(string='Annual Bonus', currency_field='currency_id')
    other_income = fields.Monetary(string='Other Income', currency_field='currency_id')
    total_income = fields.Monetary(string='Total Income', compute='_compute_totals', store=True,
                                 currency_field='currency_id')
    
    # Deductions
    pension_contributions = fields.Monetary(string='Pension Contributions', currency_field='currency_id')
    education_fund = fields.Monetary(string='Education Fund', currency_field='currency_id')
    other_deductions = fields.Monetary(string='Other Deductions', currency_field='currency_id')
    total_deductions = fields.Monetary(string='Total Deductions', compute='_compute_totals', store=True,
                                      currency_field='currency_id')
    
    # Tax details
    taxable_income = fields.Monetary(string='Taxable Income', compute='_compute_totals', store=True,
                                    currency_field='currency_id')
    calculated_tax = fields.Monetary(string='Calculated Tax', compute='_compute_tax', store=True,
                                   currency_field='currency_id')
    tax_credits = fields.Monetary(string='Tax Credits', currency_field='currency_id')
    tax_paid = fields.Monetary(string='Tax Already Paid', currency_field='currency_id')
    tax_due = fields.Monetary(string='Tax Due', compute='_compute_tax', store=True,
                            currency_field='currency_id')
    
    notes = fields.Text(string='Notes')
    
    @api.depends('annual_salary', 'annual_bonus', 'other_income', 
                 'pension_contributions', 'education_fund', 'other_deductions')
    def _compute_totals(self):
        for record in self:
            record.total_income = record.annual_salary + record.annual_bonus + record.other_income
            record.total_deductions = record.pension_contributions + record.education_fund + record.other_deductions
            record.taxable_income = max(0, record.total_income - record.total_deductions)
    
    @api.depends('taxable_income', 'tax_credits', 'tax_paid')
    def _compute_tax(self):
        for record in self:
            # Use income tax model to calculate tax
            try:
                income_tax = self.env['l10n_il.income.tax'].get_for_date(date(record.year, 12, 31))
                tax_result = income_tax.calculate_income_tax(record.taxable_income / 12, 0)
                # Multiply by 12 for annual tax
                record.calculated_tax = tax_result['income_tax'] * 12
            except Exception as e:
                _logger.error("Error calculating tax: %s", e)
                record.calculated_tax = 0
            
            record.tax_due = max(0, record.calculated_tax - record.tax_credits - record.tax_paid)
    
    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('l10n_il.income.tax.return') or _('New')
        return super().create(vals)
    
    def action_submit(self):
        for record in self:
            record.state = 'submitted'
    
    def action_approve(self):
        for record in self:
            record.state = 'approved'
    
    def action_cancel(self):
        for record in self:
            record.state = 'cancelled'
    
    def action_draft(self):
        for record in self:
            record.state = 'draft'
    
    def action_print(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.report',
            'report_name': 'l10n_il_income_tax.report_income_tax_return',
            'report_type': 'qweb-pdf',
            'data': {},
        }