from odoo import models, fields, api

class FinancialTransaction(models.Model):
    _name = 'financial.transaction'
    _description = 'Financial Transaction'
    _order = 'transaction_date desc, sequence'

    name = fields.Char('Description', required=True)
    sequence = fields.Char('Sequence Number')
    account_number = fields.Char('Account Number')
    transaction_date = fields.Date('Transaction Date')
    value_date = fields.Date('Value Date')
    amount = fields.Float('Amount', digits=(16, 2))
    currency = fields.Char('Currency', default='USD', size=3)
    reference = fields.Char('Reference')
    transaction_code = fields.Char('Transaction Code')
    raw_line = fields.Text('Raw Data')  # For debugging
    
    # Additional fields you might need
    debit_amount = fields.Float('Debit Amount', digits=(16, 2))
    credit_amount = fields.Float('Credit Amount', digits=(16, 2))
    balance = fields.Float('Balance', digits=(16, 2))
    
    @api.depends('amount')
    def _compute_debit_credit(self):
        for record in self:
            if record.amount >= 0:
                record.credit_amount = record.amount
                record.debit_amount = 0
            else:
                record.debit_amount = abs(record.amount)
                record.credit_amount = 0