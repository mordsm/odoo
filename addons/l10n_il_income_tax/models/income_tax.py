from datetime import date
from dateutil.relativedelta import relativedelta
import logging
from math import copysign

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_round, float_compare


_logger = logging.getLogger(__name__)


class IsraeliIncomeTax(models.Model):
    _name = 'l10n_il.income.tax'
    _description = 'Israeli Income Tax Calculator'
    _order = 'date_from desc, id desc'
    
    name = fields.Char(string='Name', required=True)
    date_from = fields.Date(string='Valid From', required=True)
    date_to = fields.Date(string='Valid To')
    active = fields.Boolean(default=True)
    
    tax_bracket_ids = fields.One2many(
        'l10n_il.income.tax.bracket', 'income_tax_id', 
        string='Tax Brackets', copy=True
    )
    credit_point_value = fields.Float(
        string='Credit Point Value', 
        help='Value of a single credit point in ILS',
        default=223.0
    )
    social_security_threshold = fields.Float(
        string='Social Security Threshold',
        help='Income threshold for social security rate change'
    )
    social_security_rate_under = fields.Float(
        string='Social Security Rate Under Threshold (%)',
        help='Rate for income under the threshold'
    )
    social_security_rate_over = fields.Float(
        string='Social Security Rate Over Threshold (%)',
        help='Rate for income over the threshold'
    )
    health_insurance_rate_under = fields.Float(
        string='Health Insurance Rate Under Threshold (%)',
        help='Health insurance rate for income under the threshold'
    )
    health_insurance_rate_over = fields.Float(
        string='Health Insurance Rate Over Threshold (%)',
        help='Health insurance rate for income over the threshold'
    )
    
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    
    _sql_constraints = [
        ('date_from_to_uniq', 
         'unique(date_from, date_to, company_id)', 
         'You cannot have two income tax tables that overlap!'),
    ]
    
    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for record in self:
            if record.date_to and record.date_from > record.date_to:
                raise ValidationError(_("The start date must be earlier than the end date."))
    
    @api.model
    def get_for_date(self, target_date=None):
        """Get the income tax table valid for the given date"""
        target_date = target_date or fields.Date.today()
        
        domain = [
            ('date_from', '<=', target_date),
            '|',
            ('date_to', '>=', target_date),
            ('date_to', '=', False),
            ('company_id', '=', self.env.company.id),
        ]
        
        income_tax = self.search(domain, limit=1)
        if not income_tax:
            raise UserError(_("No income tax table found for date %s", target_date))
        
        return income_tax
    
    def calculate_income_tax(self, gross_amount, credit_points=0.0):
        """
        Calculate income tax based on gross amount and credit points
        
        Args:
            gross_amount: Monthly gross salary
            credit_points: Number of credit points
            
        Returns:
            Dictionary with tax breakdown
        """
        self.ensure_one()
        
        # Sort brackets by upper limit to ensure correct calculation
        brackets = self.tax_bracket_ids.sorted(key=lambda b: b.upper_limit or float('inf'))
        
        if not brackets:
            raise UserError(_("No tax brackets defined for %s") % self.name)
        
        # Initialize calculation
        remaining_amount = gross_amount
        total_tax = 0.0
        bracket_taxes = []
        
        # Calculate tax per bracket
        for bracket in brackets:
            upper = bracket.upper_limit or float('inf')
            lower = bracket.lower_limit or 0.0
            bracket_range = upper - lower
            
            if remaining_amount <= 0:
                break
                
            # Amount taxable in this bracket
            taxable_in_bracket = min(bracket_range, remaining_amount)
            
            # Tax for this bracket
            bracket_tax = taxable_in_bracket * bracket.rate / 100.0
            total_tax += bracket_tax
            
            # Log for debugging and audit
            bracket_taxes.append({
                'bracket': f"{lower} - {upper}",
                'rate': bracket.rate,
                'taxable_amount': taxable_in_bracket,
                'tax': bracket_tax,
            })
            
            # Reduce remaining amount
            remaining_amount -= taxable_in_bracket
        
        # Apply credit points
        credit_value = self.credit_point_value * credit_points
        net_tax = max(0, total_tax - credit_value)
        
        # Calculate social security and health insurance
        ss_under, ss_over = self._calculate_social_security(gross_amount)
        hi_under, hi_over = self._calculate_health_insurance(gross_amount)
        
        total_deductions = net_tax + ss_under + ss_over + hi_under + hi_over
        net_salary = gross_amount - total_deductions
        
        return {
            'gross_amount': gross_amount,
            'bracket_taxes': bracket_taxes,
            'total_tax_before_credits': total_tax,
            'credit_points': credit_points,
            'credit_points_value': credit_value,
            'income_tax': net_tax,
            'social_security_under': ss_under,
            'social_security_over': ss_over,
            'social_security_total': ss_under + ss_over,
            'health_insurance_under': hi_under,
            'health_insurance_over': hi_over,
            'health_insurance_total': hi_under + hi_over,
            'total_deductions': total_deductions,
            'net_salary': net_salary,
        }
    
    def _calculate_social_security(self, gross_amount):
        """Calculate social security contributions"""
        if gross_amount <= self.social_security_threshold:
            return gross_amount * self.social_security_rate_under / 100.0, 0.0
        else:
            under = self.social_security_threshold * self.social_security_rate_under / 100.0
            over = (gross_amount - self.social_security_threshold) * self.social_security_rate_over / 100.0
            return under, over
    
    def _calculate_health_insurance(self, gross_amount):
        """Calculate health insurance contributions"""
        if gross_amount <= self.social_security_threshold:
            return gross_amount * self.health_insurance_rate_under / 100.0, 0.0
        else:
            under = self.social_security_threshold * self.health_insurance_rate_under / 100.0
            over = (gross_amount - self.social_security_threshold) * self.health_insurance_rate_over / 100.0
            return under, over


class IsraeliIncomeTaxBracket(models.Model):
    _name = 'l10n_il.income.tax.bracket'
    _description = 'Israeli Income Tax Bracket'
    _order = 'lower_limit'
    
    income_tax_id = fields.Many2one(
        'l10n_il.income.tax', string='Income Tax Table',
        required=True, ondelete='cascade'
    )
    name = fields.Char(compute='_compute_name', store=True)
    lower_limit = fields.Float(string='Lower Limit (ILS)', required=True)
    upper_limit = fields.Float(string='Upper Limit (ILS)')
    rate = fields.Float(string='Tax Rate (%)', required=True)
    
    @api.depends('lower_limit', 'upper_limit', 'rate')
    def _compute_name(self):
        for bracket in self:
            if bracket.upper_limit:
                bracket.name = _('%s - %s: %s%%') % (
                    bracket.lower_limit, bracket.upper_limit, bracket.rate
                )
            else:
                bracket.name = _('%s and above: %s%%') % (
                    bracket.lower_limit, bracket.rate
                )
    
    @api.constrains('lower_limit', 'upper_limit')
    def _check_limits(self):
        for bracket in self:
            if bracket.upper_limit and bracket.lower_limit >= bracket.upper_limit:
                raise ValidationError(_("The lower limit must be less than the upper limit."))
            
            # Check for overlapping brackets
            domain = [
                ('income_tax_id', '=', bracket.income_tax_id.id),
                ('id', '!=', bracket.id),
            ]
            overlapping = self.env['l10n_il.income.tax.bracket'].search(domain)
            
            for other in overlapping:
                if (not bracket.upper_limit or not other.upper_limit or
                    (bracket.lower_limit < other.upper_limit and 
                     (not bracket.upper_limit or bracket.upper_limit > other.lower_limit))):
                    raise ValidationError(_("Tax brackets cannot overlap."))


class HrEmployee(models.Model):
    _inherit = 'hr.employee'
    
    l10n_il_income_tax_credit_points = fields.Float(
        string='Income Tax Credit Points',
        default=2.25,  # Default for Israeli citizens (2.25 points)
        help='Number of credit points for income tax calculation'
    )


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'
    
    def _get_il_income_tax_data(self, contract, payslip_date):
        """Get income tax data for calculating Israeli payslip"""
        income_tax = self.env['l10n_il.income.tax'].get_for_date(payslip_date)
        credit_points = contract.employee_id.l10n_il_income_tax_credit_points
        
        # Get the taxable gross amount from payslip lines
        gross_amount = 0.0
        for line in self.line_ids:
            if line.category_id.code == 'GROSS':
                gross_amount += line.amount
        
        # Calculate income tax
        tax_data = income_tax.calculate_income_tax(gross_amount, credit_points)
        return tax_data