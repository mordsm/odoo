# -*- coding: utf-8 -*-

from datetime import date, datetime
from dateutil.relativedelta import relativedelta
import logging
import json

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


_logger = logging.getLogger(__name__)


class IncomeTaxReportWizard(models.TransientModel):
    _name = 'l10n_il.income.tax.report.wizard'
    _description = 'Income Tax Report Wizard'
    
    # Report parameters
    date_from = fields.Date(string='From Date', required=True, default=lambda self: date(date.today().year, 1, 1))
    date_to = fields.Date(string='To Date', required=True, default=lambda self: date(date.today().year, 12, 31))
    employee_ids = fields.Many2many('hr.employee', string='Employees')
    department_id = fields.Many2one('hr.department', string='Department')
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    
    report_type = fields.Selection([
        ('summary', 'Summary Report'),
        ('detailed', 'Detailed Report'),
        ('official', 'Official Tax Form')
    ], string='Report Type', default='summary', required=True)
    
    include_social_security = fields.Boolean(string='Include Social Security', default=True)
    include_health_insurance = fields.Boolean(string='Include Health Insurance', default=True)
    
    # Report output
    report_data = fields.Text(string='Report Data', readonly=True)
    
    @api.onchange('department_id')
    def _onchange_department_id(self):
        """Filter employees based on department selection"""
        if self.department_id:
            return {'domain': {'employee_ids': [('department_id', '=', self.department_id.id)]}}
        return {'domain': {'employee_ids': []}}
    
    def action_generate_report(self):
        """Generate the income tax report based on selected criteria"""
        self.ensure_one()
        
        # Basic validation
        if self.date_from > self.date_to:
            raise ValidationError(_("Start date must be before end date"))
        
        # Determine employees to include
        employees = self.employee_ids
        if not employees and self.department_id:
            employees = self.env['hr.employee'].search([
                ('department_id', '=', self.department_id.id),
                ('company_id', '=', self.company_id.id)
            ])
        elif not employees:
            employees = self.env['hr.employee'].search([
                ('company_id', '=', self.company_id.id)
            ])
        
        if not employees:
            raise UserError(_("No employees found matching the selected criteria"))
        
        # Get the income tax configuration for the period
        try:
            income_tax = self.env['l10n_il.income.tax'].get_for_date(self.date_to)
        except Exception as e:
            raise UserError(_("Error getting income tax configuration: %s") % str(e))
        
        # Collect data for each employee
        report_data = {
            'company': {
                'name': self.company_id.name,
                'vat': self.company_id.vat,
                'l10n_il_company_id': self.company_id.l10n_il_company_id if hasattr(self.company_id, 'l10n_il_company_id') else '',
            },
            'period': {
                'date_from': self.date_from.strftime('%Y-%m-%d'),
                'date_to': self.date_to.strftime('%Y-%m-%d'),
            },
            'report_type': self.report_type,
            'employees': []
        }
        
        # Process each employee
        for employee in employees:
            employee_data = self._get_employee_data(employee)
            report_data['employees'].append(employee_data)
        
        # Store report data
        self.report_data = json.dumps(report_data)
        
        # Return appropriate action based on report type
        if self.report_type == 'official':
            return self._generate_official_report()
        else:
            return self._generate_standard_report()
    
    def _get_employee_data(self, employee):
        """Collect tax data for a specific employee"""
        # Find payslips in the period
        payslips = self.env['hr.payslip'].search([
            ('employee_id', '=', employee.id),
            ('date_from', '>=', self.date_from),
            ('date_to', '<=', self.date_to),
            ('state', 'in', ['done', 'paid']),
        ])
        
        # Initialize totals
        total_gross = 0.0
        total_net = 0.0
        total_income_tax = 0.0
        total_social_security = 0.0
        total_health_insurance = 0.0
        
        # Process payslips
        payslip_data = []
        for payslip in payslips:
            # Extract line values
            gross_amount = sum(line.total for line in payslip.line_ids if line.code == 'GROSS')
            net_amount = sum(line.total for line in payslip.line_ids if line.code == 'NET')
            income_tax = sum(line.total for line in payslip.line_ids if line.code == 'IT')
            social_security = sum(line.total for line in payslip.line_ids if line.code == 'SS')
            health_insurance = sum(line.total for line in payslip.line_ids if line.code == 'HI')
            
            # Add to totals
            total_gross += gross_amount
            total_net += net_amount
            total_income_tax += income_tax
            total_social_security += social_security
            total_health_insurance += health_insurance
            
            # Add payslip details if detailed report
            if self.report_type == 'detailed':
                payslip_data.append({
                    'name': payslip.name,
                    'period': payslip.date_from.strftime('%Y-%m-%d') + ' to ' + payslip.date_to.strftime('%Y-%m-%d'),
                    'gross': gross_amount,
                    'net': net_amount,
                    'income_tax': income_tax,
                    'social_security': social_security,
                    'health_insurance': health_insurance,
                })
        
        # Build employee data structure
        employee_data = {
            'id': employee.id,
            'name': employee.name,
            'identification_id': employee.identification_id or '',
            'department': employee.department_id.name if employee.department_id else '',
            'job_title': employee.job_title or '',
            'credit_points': getattr(employee, 'l10n_il_income_tax_credit_points', 0.0),
            'totals': {
                'gross': total_gross,
                'net': total_net,
                'income_tax': total_income_tax,
                'social_security': total_social_security,
                'health_insurance': total_health_insurance,
            }
        }
        
        # Add payslip details if detailed report
        if self.report_type == 'detailed':
            employee_data['payslips'] = payslip_data
            
        return employee_data
    
    def _generate_standard_report(self):
        """Generate standard HTML/PDF report"""
        self.ensure_one()
        report_name = 'summary' if self.report_type == 'summary' else 'detailed'
        return {
            'type': 'ir.actions.report',
            'report_name': f'l10n_il_income_tax.report_{report_name}',
            'report_type': 'qweb-pdf',
            'data': {'wizard_id': self.id},
        }
    
    def _generate_official_report(self):
        """Generate official tax form report"""
        self.ensure_one()
        return {
            'type': 'ir.actions.report',
            'report_name': 'l10n_il_income_tax.report_official_form',
            'report_type': 'qweb-pdf',
            'data': {'wizard_id': self.id},
        }