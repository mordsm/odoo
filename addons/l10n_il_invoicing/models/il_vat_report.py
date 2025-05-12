from odoo import api, fields, models, _
from odoo.exceptions import UserError
from datetime import datetime, timedelta
import base64
import logging
import re
import base64
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class IsraeliVatReport(models.Model):
    _name = 'l10n.il.vat.report'
    _description = 'Israeli VAT Report'
    _order = 'date_from desc'
    
    name = fields.Char('Report Name', required=True)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    date_from = fields.Date('Start Date', required=True)
    date_to = fields.Date('End Date', required=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('calculated', 'Calculated'),
        ('done', 'Submitted'),
    ], string='Status', default='draft')
    
    # Summary fields
    output_vat_base = fields.Monetary('Output VAT Base', readonly=True)
    output_vat_tax = fields.Monetary('Output VAT Amount', readonly=True)
    input_vat_base = fields.Monetary('Input VAT Base', readonly=True)
    input_vat_tax = fields.Monetary('Input VAT Amount', readonly=True)
    export_vat_base = fields.Monetary('Export Base (Zero-rated)', readonly=True)
    import_vat_base = fields.Monetary('Import Base', readonly=True)
    import_vat_tax = fields.Monetary('Import VAT Amount', readonly=True)
    exempt_vat_base = fields.Monetary('Exempt Transactions', readonly=True)
    vat_payable = fields.Monetary('VAT Payable', readonly=True)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')
    
    # File generation fields
    report_file = fields.Binary('Download Report')
    report_filename = fields.Char('Report Filename')
    
    # Technical fields for line items
    line_ids = fields.One2many('l10n.il.vat.report.line', 'report_id', string='Report Lines')
    
    @api.model
    def create(self, vals):
        """Override create to set default name if not provided"""
        if not vals.get('name') and vals.get('date_from') and vals.get('date_to'):
            date_from = fields.Date.to_date(vals['date_from'])
            date_to = fields.Date.to_date(vals['date_to'])
            vals['name'] = _('VAT Report %s - %s') % (
                date_from.strftime('%d/%m/%Y'),
                date_to.strftime('%d/%m/%Y')
            )
        return super(IsraeliVatReport, self).create(vals)
   
    def action_calculate(self):
        self.ensure_one()
        if self.state != 'draft':
            return
        
        # Clear previous calculations
        self.line_ids.unlink()
    
        # Get all invoices in the date range
        domain = [
            ('company_id', '=', self.company_id.id),
            ('date', '>=', self.date_from),
            ('date', '<=', self.date_to),
            ('state', 'in', ['posted']),  # Only include posted invoices
        ]
    
        moves = self.env['account.move'].search(domain)
    
        # Debug output - add this to check what moves are found
        _logger.info(f"Found {len(moves)} moves for VAT report calculation")
    
        # Create report lines
        for move in moves:
            vals = {
                'report_id': self.id,
                'move_id': move.id,
                'partner_id': move.partner_id.id,
                'date': move.date,
                'move_type': move.move_type,
                'amount_untaxed': move.amount_untaxed_signed,
                'amount_tax': move.amount_tax_signed,
                'amount_total': move.amount_total_signed,
            }
            self.env['l10n.il.vat.report.line'].create(vals)
    
        # Calculate summary values
        self._calculate_summary_values()
    
        self.state = 'calculated'
        return True



    def _calculate_summary_values(self):
        """Calculate summary values for the VAT report."""
        self.ensure_one()
    
        # Initialize summary values
        output_vat_base = 0.0
        output_vat_tax = 0.0
        input_vat_base = 0.0
        input_vat_tax = 0.0
        export_vat_base = 0.0
        import_vat_base = 0.0
        import_vat_tax = 0.0
        exempt_vat_base = 0.0
    
        # Group and sum values based on tax groups and move types
        for line in self.line_ids:
            move = line.move_id
        
            # Sales invoices (output VAT)
            if move.move_type in ('out_invoice', 'out_refund'):
                sign = -1 if move.move_type == 'out_refund' else 1
            
                # Check for export (zero-rated) transactions
                is_export = False
                for tax_line in move.line_ids.filtered(lambda l: l.tax_line_id):
                    # Check if this is a zero-rated tax (export)
                    if tax_line.tax_line_id.amount == 0 and tax_line.tax_line_id.name and 'יצוא' in tax_line.tax_line_id.name:
                        is_export = True
                        break
            
                if is_export:
                    export_vat_base += sign * line.amount_untaxed
                else:
                    # Regular domestic sales
                    output_vat_base += sign * line.amount_untaxed
                    output_vat_tax += sign * line.amount_tax
        
            # Purchase invoices (input VAT)
            elif move.move_type in ('in_invoice', 'in_refund'):
                sign = -1 if move.move_type == 'in_refund' else 1
            
                # Check for import transactions
                is_import = False
                for tax_line in move.line_ids.filtered(lambda l: l.tax_line_id):
                    # Check if this is an import tax
                    if tax_line.tax_line_id.name and 'יבוא' in tax_line.tax_line_id.name:
                        is_import = True
                        break
            
                if is_import:
                    import_vat_base += sign * line.amount_untaxed
                    import_vat_tax += sign * line.amount_tax
                else:
                    # Regular domestic purchases
                    input_vat_base += sign * line.amount_untaxed
                    input_vat_tax += sign * line.amount_tax
    
        # Check for exempt transactions (implement based on your tax configuration)
        # This is a simplified example, you may need to adjust based on your specific tax setup
        exempt_moves = self.env['account.move'].search([
            ('invoice_date', '>=', self.date_from),
            ('invoice_date', '<=', self.date_to),
            ('state', '=', 'posted'),
            ('move_type', 'in', ['out_invoice', 'out_refund']),
            ('company_id', '=', self.company_id.id),
        ])
    
        for move in exempt_moves:
            for line in move.invoice_line_ids:
                # Check for exempt tax groups
                for tax in line.tax_ids:
                    if tax.amount == 0 and tax.name and 'פטור' in tax.name:
                        sign = -1 if move.move_type == 'out_refund' else 1
                        exempt_vat_base += sign * line.price_subtotal
    
        # Update the report with calculated values
        self.write({
            'output_vat_base': output_vat_base,
            'output_vat_tax': output_vat_tax,
            'input_vat_base': input_vat_base,
            'input_vat_tax': input_vat_tax,
            'export_vat_base': export_vat_base,
            'import_vat_base': import_vat_base,
            'import_vat_tax': import_vat_tax,
            'exempt_vat_base': exempt_vat_base,
            'vat_payable': output_vat_tax - input_vat_tax - import_vat_tax
        })

    
    def action_draft(self):
        """Reset to draft"""
        self.ensure_one()
        self.state = 'draft'
        return True
 
    def action_generate_file(self):
        self.ensure_one()
        if self.state != 'calculated':
            return
        
        # Format date for file name (MMYYYY)
        report_date = fields.Date.from_string(self.date_to)
        period = report_date.strftime('%m%Y')
    
        # Get company VAT number (remove non-digits)
        vat_number = re.sub(r'\D', '', self.company_id.vat or '')
        if not vat_number:
            raise UserError(_("Please set a valid VAT number for the company."))
    
        # Create header record (fixed format according to Israeli Tax Authority)
        lines = []
    
        # Record type 874: PCN874 file header
        # Format: 874 + VAT number (9 digits) + reporting period (MMYYYY) + padding
        header = f"874{vat_number.ljust(9)}{period}{''.ljust(15)}"
        lines.append(header)
    
        # Record type C: Company details
        # Format: C + company name (padded to 50 chars) + contact info
        company_name = self.company_id.name or ''
        company_name = company_name[:50].ljust(50)  # Limit to 50 chars
        company_phone = self.company_id.phone or ''
        company_phone = company_phone[:15].ljust(15)  # Limit to 15 chars
    
        c_record = f"C{company_name}{company_phone}"
        lines.append(c_record)
    
        # Record type D: Summary record
        # Format: D + reporting month (2 digits) + year (4 digits) + exempt transactions + income + tax + expenses + tax + imports
        month = report_date.strftime('%m')
        year = report_date.strftime('%Y')
    
        # Format all amounts as integers in agorot (cents)
        exempt_amount = int(self.exempt_vat_base * 100)
        output_base = int(self.output_vat_base * 100)
        output_tax = int(self.output_vat_tax * 100)
        input_base = int(self.input_vat_base * 100)
        input_tax = int(self.input_vat_tax * 100)
        import_base = int(self.import_vat_base * 100)
        import_tax = int(self.import_vat_tax * 100)
    
        # Format the D record with proper padding for each field
        d_record = f"D{month}{year}"
        d_record += f"{exempt_amount:012d}"      # 12 digits for exempt amount
        d_record += f"{output_base:012d}"        # 12 digits for output base
        d_record += f"{output_tax:012d}"         # 12 digits for output tax
        d_record += f"{input_base:012d}"         # 12 digits for input base
        d_record += f"{input_tax:012d}"          # 12 digits for input tax
        d_record += f"{import_base:012d}"        # 12 digits for import base
        d_record += f"{import_tax:012d}"         # 12 digits for import tax
        d_record += f"{''.ljust(27, '0')}"       # Padding with zeros
    
        lines.append(d_record)
    
        # Record type M: Detailed transactions (optional)
        # This is often required for electronic submissions
        # For each transaction in line_ids
        for line in self.line_ids:
            # Skip lines with zero amounts
            if line.amount_total == 0:
                continue
            
            # Get partner VAT number (if available)
            partner_vat = ''
            if line.partner_id and line.partner_id.vat:
                partner_vat = re.sub(r'\D', '', line.partner_id.vat)
            
            # Get the transaction date in DDMMYYYY format
            tx_date = fields.Date.from_string(line.date).strftime('%d%m%Y')
        
            # Determine transaction type code
            if line.move_id.move_type == 'out_invoice':
                tx_type = '1'  # Sales invoice
            elif line.move_id.move_type == 'out_refund':
                tx_type = '2'  # Sales credit note
            elif line.move_id.move_type == 'in_invoice':
                tx_type = '3'  # Purchase invoice
            elif line.move_id.move_type == 'in_refund':
                tx_type = '4'  # Purchase credit note
            else:
                tx_type = '0'  # Other
            
            # Format the amount in agorot (cents)
            tx_amount = int(abs(line.amount_total) * 100)
        
            # Get document reference number
            doc_ref = line.move_id.name or ''
            doc_ref = re.sub(r'[^0-9a-zA-Z]', '', doc_ref)  # Remove special characters
            doc_ref = doc_ref[:20].ljust(20)  # Limit to 20 chars
        
            # Format the M record
            m_record = f"M{tx_type}{partner_vat.ljust(9)}{tx_date}{tx_amount:010d}{doc_ref}"
            lines.append(m_record)
    
        # Generate file content
        content = '\r\n'.join(lines)
    
        # Save as attachment
        filename = f"PCN874_{vat_number}_{period}.txt"
        self.write({
            'report_file': base64.b64encode(content.encode('windows-1255')),  # Use Windows Hebrew encoding
            'report_filename': filename,
            'state': 'done'
        })
    
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('VAT report file has been generated successfully.'),
                'type': 'success',
                'sticky': False,
            }
        }
    @api.onchange('date_from')
    def _onchange_date_from(self):
        """Set date_to as end of month when date_from changes"""
        if self.date_from:
            date = fields.Date.from_string(self.date_from)
            # Get last day of the month
            if date.month == 12:
                last_day = date.replace(day=31)
            else:
                last_day = date.replace(month=date.month+1, day=1) - timedelta(days=1)
            self.date_to = last_day


class IsraeliVatReportLine(models.Model):
    _name = 'l10n.il.vat.report.line'
    _description = 'Israeli VAT Report Line'
    
    report_id = fields.Many2one('l10n.il.vat.report', string='Report', ondelete='cascade')
    move_id = fields.Many2one('account.move', string='Invoice')
    partner_id = fields.Many2one('res.partner', string='Partner')
    move_type = fields.Selection(related='move_id.move_type')
    date = fields.Date('Date')
    amount_untaxed = fields.Monetary('Base Amount')
    amount_tax = fields.Monetary('Tax Amount')
    amount_total = fields.Monetary('Total Amount')
    currency_id = fields.Many2one('res.currency', related='report_id.currency_id')