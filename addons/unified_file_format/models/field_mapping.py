from odoo import models, fields, api

class FieldMapping(models.Model):
    _name = 'unified.file.format.mapping'
    _description = 'Field Mapping Configuration'

    name = fields.Char('Mapping Name', required=True)
    model_name = fields.Char('Target Model', required=True)
    description = fields.Text('Description')
    
    mapping_line_ids = fields.One2many('unified.file.format.mapping.line', 'mapping_id', string='Field Mappings')

class FieldMappingLine(models.Model):
    _name = 'unified.file.format.mapping.line'
    _description = 'Field Mapping Line'

    mapping_id = fields.Many2one('unified.file.format.mapping', string='Mapping', ondelete='cascade')
    external_field = fields.Char('External Field', required=True)
    odoo_field = fields.Char('Odoo Field', required=True)
    data_type = fields.Selection([
        ('string', 'String'),
        ('integer', 'Integer'),
        ('float', 'Float'),
        ('boolean', 'Boolean'),
        ('date', 'Date'),
        ('datetime', 'DateTime')
    ], string='Data Type', default='string')
    default_value = fields.Char('Default Value')