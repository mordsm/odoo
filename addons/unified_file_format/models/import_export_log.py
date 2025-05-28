from odoo import models, fields

class ImportExportLog(models.Model):
    _name = 'unified.file.format.log'
    _description = 'Import Export Operation Log'
    _order = 'create_date desc'

    operation_id = fields.Many2one('unified.file.format', string='Operation', ondelete='cascade')
    log_type = fields.Selection([
        ('info', 'Information'),
        ('warning', 'Warning'),
        ('error', 'Error')
    ], string='Type', required=True)
    message = fields.Text('Message', required=True)
    record_data = fields.Text('Record Data')