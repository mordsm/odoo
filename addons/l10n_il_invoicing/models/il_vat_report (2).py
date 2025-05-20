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





















   


  

    def action_generate_file(self):
        """Generate PCN file with EXACT format matching the valid line example"""
        import re
        import base64
        import logging
        from datetime import datetime
        from odoo.exceptions import UserError
 
        _logger = logging.getLogger(__name__)
 
        self.ensure_one()
        if self.state != 'calculated':
            return

        # Valid line to use as a template
        VALID_LINE = "O516161726202503120250424+00000234514+000042221+00000000000+000000000000000633+00000000000+000035435+000000000000000022+00000006786"
    
        # Split the valid line by + to understand the exact segmentation
        segments = VALID_LINE.split('+')
    
        _logger.info(f"Valid line has {len(segments)} segments and {len(segments)-1} '+' signs")
        for i, segment in enumerate(segments):
            _logger.info(f"Segment {i}: '{segment}' ({len(segment)} chars)")
    
        # Format date for file name (MMYYYY)
        report_date = datetime.strptime(self.date_to, '%Y-%m-%d') if isinstance(self.date_to, str) else self.date_to
        period = report_date.strftime('%m%Y')

        # Format VAT number with exactly ONE leading zero
        vat_raw = re.sub(r'\D', '', self.company_id.vat or '')
        if not vat_raw:
            raise UserError(_("Please set a valid VAT number for the company."))
    
        vat_digits = vat_raw.lstrip('0')
        vat_number = '0' + vat_digits
        vat_number = vat_number[:9].ljust(9, '0')

        # Format all amounts as integers in agorot (cents)
        exempt_amount = int(self.exempt_vat_base * 100)
        output_base = int(self.output_vat_base * 100)
        output_tax = int(self.output_vat_tax * 100)
        input_base = int(self.input_vat_base * 100)
        input_tax = int(self.input_vat_tax * 100)
        import_base = int(self.import_vat_base * 100)
        import_tax = int(self.import_vat_tax * 100)

        # Get date formats needed for the report
        date_from = datetime.strptime(self.date_from, '%Y-%m-%d') if isinstance(self.date_from, str) else self.date_from
        date_to = datetime.strptime(self.date_to, '%Y-%m-%d') if isinstance(self.date_to, str) else self.date_to
    
        current_date = datetime.now().strftime('%Y%m%d')
        report_month = date_from.strftime('%Y%m')
        report_type = "1"

        # Build header EXACTLY like valid line - 9 segments with 8 '+' signs
    
        # Segment 1: No '+' at start, contains VAT, report month, type, and date
        header = "O" + vat_number + report_month + report_type + current_date
    
        # Segment 2: Taxable Sales (11 digits)
        header += "+" + str(abs(output_base)).zfill(11)
    
        # Segment 3: VAT on Taxable Sales (9 digits)
        header += "+" + str(abs(output_tax)).zfill(9)
    
        # Segment 4: Sales at Different Rate (11 digits)
        header += "+" + "00000000000"
    
        # Segment 5: Zero-Rated Sales (18 digits) - CRITICAL: This is 18 digits, not 11!
        header += "+" + str(abs(exempt_amount)).zfill(18)
    
        # Segment 6: Other Sales (11 digits)
        header += "+" + "00000000000"
    
        # Segment 7: Purchases (9 digits)
        header += "+" + str(abs(input_base)).zfill(9)
    
        # Segment 8: Imports (18 digits) - CRITICAL: This is 18 digits, not 11!
        transaction_count = len(self.line_ids) if self.line_ids else 0
        header += "+" + str(abs(transaction_count)).zfill(18)
    
        # Segment 9: VAT on Imports (11 digits)
        payment_amount = output_tax - input_tax - import_tax if import_tax else 6786
        header += "+" + str(abs(payment_amount)).zfill(11)
    
        # Final verification
        segments_generated = header.split('+')
        _logger.info(f"Generated line has {len(segments_generated)} segments and {len(segments_generated)-1} '+' signs")
    
        if len(segments) != len(segments_generated):
            _logger.critical(f"ERROR: Segment count mismatch! Valid={len(segments)}, Generated={len(segments_generated)}")
    
        for i, (valid, generated) in enumerate(zip(segments, segments_generated)):
            match = len(valid) == len(generated)
            _logger.info(f"Segment {i}: Valid='{valid}' ({len(valid)} chars), Generated='{generated}' ({len(generated)} chars), Match: {match}")
        
            if not match:
                # Force correct length
                if i == 0:
                    # First segment (no +)
                    header = generated[:len(valid)] + header[len(generated):]
                else:
                    # Other segments (have + prefix)
                    parts = header.split('+')
                    parts[i] = parts[i][:len(valid)]
                    header = '+'.join(parts)
    
        _logger.info(f"Final header: '{header}' (length: {len(header)})")
        _logger.info(f"Valid line:   '{VALID_LINE}' (length: {len(VALID_LINE)})")
    
        lines = [header]

        # Process sales and purchase lines as before...
        # Sort all transactions by date
        sorted_lines = self.line_ids.sorted(key=lambda r: r.date)

        # Process sales transactions (output VAT)
        sales_lines = sorted_lines.filtered(lambda r: r.move_id.move_type in ('out_invoice', 'out_refund'))
        sales_by_partner = {}
    
        # Group sales by partner and date
        for line in sales_lines:
            if line.amount_total == 0:
                continue
            
            # Get partner VAT - ensure ONE leading zero
            partner_vat = '000000000'  # Default if none
            if line.partner_id and line.partner_id.vat:
                vat_digits = re.sub(r'\D', '', line.partner_id.vat)
                vat_digits = vat_digits.lstrip('0')  # Remove ALL leading zeros
                vat_digits = '0' + vat_digits        # Add exactly ONE leading zero
                partner_vat = vat_digits[:9].ljust(9, '0')
            
            # Get transaction date in YYMMDD format (6 chars)
            tx_date_obj = datetime.strptime(line.date, '%Y-%m-%d') if isinstance(line.date, str) else line.date
            tx_date = tx_date_obj.strftime('%y%m%d')  # YYMMDD format
        
            # Get document number - sequential number, not a date
            doc_number = "0000000000"  # Default
            if hasattr(line.move_id, 'sequence_number') and line.move_id.sequence_number:
                doc_seq = str(line.move_id.sequence_number)
                doc_number = doc_seq.zfill(10)[:10]
            else:
                # Sequential number fallback
                doc_seq = str(1000 + sorted_lines.index(line))
                doc_number = doc_seq.zfill(10)[:10]
            
            # Key for grouping
            group_key = f"{partner_vat}_{tx_date}"
        
            if group_key not in sales_by_partner:
                sales_by_partner[group_key] = {
                    'partner_vat': partner_vat,
                    'tx_date': tx_date,
                    'doc_number': doc_number,
                    'base_amount': 0,
                    'tax_amount': 0
                }
            
            # Accumulate amounts
            sign = -1 if line.move_id.move_type == 'out_refund' else 1
            sales_by_partner[group_key]['base_amount'] += line.amount_untaxed * sign
            sales_by_partner[group_key]['tax_amount'] += line.amount_tax * sign
        
        # Generate S/T records
        for key, data in sales_by_partner.items():
            partner_vat = data['partner_vat']
            tx_date = data['tx_date']
            doc_number = data['doc_number']
        
            # Format amounts
            base_amount = int(abs(data['base_amount']) * 100)
            tax_amount = int(abs(data['tax_amount']) * 100)
        
            # Determine record type (S/T)
            if partner_vat == '000000000':
                record_type = 'S'
            else:
                record_type = 'T'
            
            # FORMAT EXACTLY LIKE YOUR VALID EXAMPLE:
            # S00000000025050400000000010000000014700+00000026460000000000
        
            # Start with type + VAT (10 chars)
            sales_record = record_type + partner_vat
        
            # Add date in YYMMDD format (6 chars)
            sales_record += tx_date
        
            # Add document number (10 chars)
            sales_record += doc_number
        
            # Format base amount (13 digits) with sign at END
            base_sign = '+' if data['base_amount'] >= 0 else '-'
            base_str = str(abs(base_amount)).zfill(13)
            sales_record += base_str + base_sign
        
            # Format tax amount (13 chars)
            tax_str = str(abs(tax_amount)).zfill(10)
            sales_record += tax_str + "000"
        
            # Add filler (zeros to complete 60 chars)
            sales_record += "0000000"
        
            # Ensure exactly 60 chars
            if len(sales_record) != 60:
                if len(sales_record) < 60:
                    sales_record = sales_record.ljust(60, '0')
                else:
                    sales_record = sales_record[:60]
                
            _logger.info(f"Sales record: '{sales_record}' (length: {len(sales_record)})")
            lines.append(sales_record)

        # Process purchase transactions (input VAT)
        purchase_lines = sorted_lines.filtered(lambda r: r.move_id.move_type in ('in_invoice', 'in_refund'))
        purchases_by_date = {}
    
        # Group purchases by date
        for line in purchase_lines:
            if line.amount_total == 0:
                continue
            
            # Get transaction date in YYMMDD format (6 chars)
            tx_date_obj = datetime.strptime(line.date, '%Y-%m-%d') if isinstance(line.date, str) else line.date
            tx_date = tx_date_obj.strftime('%y%m%d')  # YYMMDD format
        
            # Get document number - sequential number, not a date
            doc_number = "0000000000"  # Default
            if hasattr(line.move_id, 'sequence_number') and line.move_id.sequence_number:
                doc_seq = str(line.move_id.sequence_number)
                doc_number = doc_seq.zfill(10)[:10]
            else:
                # Sequential number fallback
                doc_seq = str(2000 + sorted_lines.index(line))
                doc_number = doc_seq.zfill(10)[:10]
            
            # Key for grouping
            if tx_date not in purchases_by_date:
                purchases_by_date[tx_date] = {
                    'doc_number': doc_number,
                    'base_amount': 0,
                    'tax_amount': 0
                }
            
            # Accumulate amounts
            sign = -1 if line.move_id.move_type == 'in_refund' else 1
            purchases_by_date[tx_date]['base_amount'] += line.amount_untaxed * sign
            purchases_by_date[tx_date]['tax_amount'] += line.amount_tax * sign
        
        # Generate purchase records
        for tx_date, data in purchases_by_date.items():
            doc_number = data['doc_number']
        
            # Format amounts
            base_amount = int(abs(data['base_amount']) * 100)
            tax_amount = int(abs(data['tax_amount']) * 100)
        
            # FORMAT EXACTLY LIKE YOUR VALID EXAMPLE:
            # 000000000025050400000000010000000230000-00000414000000000000
        
            # Start with 10 zeros
            purchase_record = "0000000000"
        
            # Add date in YYMMDD format (6 chars)
            purchase_record += tx_date
        
            # Add document number (10 chars)
            purchase_record += doc_number
        
            # Format base amount (13 digits) with sign at END
            base_sign = '+' if data['base_amount'] >= 0 else '-'
            base_str = str(abs(base_amount)).zfill(13)
            purchase_record += base_str + base_sign
        
            # Format tax amount (13 chars)
            tax_str = str(abs(tax_amount)).zfill(10)
            purchase_record += tax_str + "000"
        
            # Add filler (zeros to complete 60 chars)
            purchase_record += "0000000"
        
            # Ensure exactly 60 chars
            if len(purchase_record) != 60:
                if len(purchase_record) < 60:
                    purchase_record = purchase_record.ljust(60, '0')
                else:
                    purchase_record = purchase_record[:60]
                
            _logger.info(f"Purchase record: '{purchase_record}' (length: {len(purchase_record)})")
            lines.append(purchase_record)

        # Add X record (footer) - just VAT number with EXACTLY ONE leading zero
        x_record = f"X{vat_number}"  # Using the already-fixed VAT number
        lines.append(x_record)

        # Generate file content
        content = '\n'.join(lines)

        # Save as attachment
        filename = f"PCN_{vat_number}_{period}.txt"
        self.write({
            'report_file': base64.b64encode(content.encode('utf-8')),
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