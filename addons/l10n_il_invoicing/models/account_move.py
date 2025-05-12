from odoo import api, fields, models, _


class AccountMove(models.Model):
    _inherit = 'account.move'
    
    l10n_il_vat_transaction_type = fields.Selection([
        ('regular', 'Regular Transaction'),
        ('capital_asset', 'Capital Asset'),
        ('import', 'Import'),
        ('export', 'Export'),
    ], string='VAT Transaction Type', default='regular',
       help="Used for proper categorization in Israeli VAT reports")
    
    # Optional: Add fields for Israeli-specific document numbers if needed
    l10n_il_document_number = fields.Char('Israeli Document Number')
    
    @api.model
    def _l10n_il_prepare_vat_report_data(self, date_from, date_to):
        """
        Prepares data for the Israeli VAT report
        :param date_from: Start date of the report period
        :param date_to: End date of the report period
        :return: Dictionary with prepared data
        """
        domain = [
            ('state', '=', 'posted'),
            ('move_type', 'in', ['out_invoice', 'out_refund', 'in_invoice', 'in_refund']),
            ('date', '>=', date_from),
            ('date', '<=', date_to),
        ]
        
        # Get all relevant invoices for the period
        invoices = self.search(domain)
        
        # Initialize result structure
        result = {
            'output_vat': {'base': 0.0, 'tax': 0.0},
            'input_vat': {'base': 0.0, 'tax': 0.0},
            'export_vat': {'base': 0.0, 'tax': 0.0},
            'import_vat': {'base': 0.0, 'tax': 0.0},
            'exempt_vat': {'base': 0.0},
            'invoices': {},
        }
        
        # Process each invoice
        for invoice in invoices:
            sign = -1 if invoice.move_type in ['out_refund', 'in_refund'] else 1
            is_sale = invoice.move_type in ['out_invoice', 'out_refund']
            is_purchase = not is_sale
            
            # Get invoice details
            invoice_data = {
                'id': invoice.id,
                'name': invoice.name,
                'partner': invoice.partner_id.name,
                'date': invoice.date,
                'amount_total': invoice.amount_total,
                'amount_tax': invoice.amount_tax,
                'amount_untaxed': invoice.amount_untaxed,
                'tax_details': [],
            }
            
            # Process tax details
            for line in invoice.invoice_line_ids:
                for tax in line.tax_ids:
                    # Calculate tax amount for this line
                    base_amount = line.price_subtotal * sign
                    tax_amount = base_amount * (tax.amount / 100)
                    
                    # Add to the appropriate category
                    tax_data = {
                        'name': tax.name,
                        'base': base_amount,
                        'amount': tax_amount,
                        'rate': tax.amount,
                    }
                    invoice_data['tax_details'].append(tax_data)
                    
                    # Categorize based on tax configuration
                    if tax.l10n_il_vat_category == 'standard':
                        if is_sale:
                            result['output_vat']['base'] += base_amount
                            result['output_vat']['tax'] += tax_amount
                        else:
                            result['input_vat']['base'] += base_amount
                            result['input_vat']['tax'] += tax_amount
                    elif tax.l10n_il_vat_category == 'export':
                        result['export_vat']['base'] += base_amount
                    elif tax.l10n_il_vat_category == 'import':
                        result['import_vat']['base'] += base_amount
                        result['import_vat']['tax'] += tax_amount
                    elif tax.l10n_il_vat_category in ['exempt', 'out_of_scope']:
                        result['exempt_vat']['base'] += base_amount
            
            # Store invoice details
            result['invoices'][invoice.id] = invoice_data
            
        return result