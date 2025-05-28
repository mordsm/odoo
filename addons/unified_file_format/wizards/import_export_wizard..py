from odoo import models, fields, api, exceptions

class ImportExportWizard(models.TransientModel):
    _name = 'unified.file.format.wizard'
    _description = 'Import/Export Wizard'

    operation_type = fields.Selection([
        ('import', 'Import File to Odoo'),
        ('export', 'Export Odoo to File')
    ], string='Operation', required=True, default='import')
    
    model_name = fields.Char('Target Model', required=True, default='res.partner')
    
    # Import fields
    import_file = fields.Binary('Import File', help="Select CSV file to import")
    import_filename = fields.Char('Filename')
    field_mapping_id = fields.Many2one('unified.file.format.mapping', string='Field Mapping')
    
    # Export fields
    export_format = fields.Selection([
        ('csv', 'CSV')
    ], string='Export Format', default='csv')
    domain_filter = fields.Text('Domain Filter', help="e.g., [('active','=',True)]")
    field_list = fields.Text('Fields to Export', help="Comma-separated field names")
    
    @api.model
    def default_get(self, fields_list):
        """Set default values"""
        defaults = super().default_get(fields_list)
        
        # Set model from context if available
        if self.env.context.get('active_model'):
            defaults['model_name'] = self.env.context['active_model']
            
        return defaults

    def action_import(self):
        """Execute import operation"""
        if not self.import_file:
            raise exceptions.UserError("Please select a file to import.")
        
        if not self.model_name:
            raise exceptions.UserError("Please specify the target model.")
        
        # Check if target model exists
        try:
            self.env[self.model_name]
        except KeyError:
            raise exceptions.UserError(f"Model '{self.model_name}' does not exist.")
        
        # Create operation record
        operation = self.env['unified.file.format'].create({
            'name': f"Import {self.import_filename or 'file'} to {self.model_name}",
            'operation_type': 'import',
            'model_name': self.model_name,
            'file_name': self.import_filename,
            'file_data': self.import_file,
            'file_format': 'csv',
            'state': 'draft'
        })
        
        # Prepare field mappings
        field_mappings = {}
        if self.field_mapping_id:
            for line in self.field_mapping_id.mapping_line_ids:
                field_mappings[line.external_field] = line.odoo_field
        
        # Perform import
        try:
            result = operation.perform_import(
                self.model_name, 
                self.import_file, 
                self.import_filename,
                field_mappings if field_mappings else None
            )
            
            return {
                'type': 'ir.actions.act_window',
                'name': 'Import Result',
                'res_model': 'unified.file.format',
                'res_id': operation.id,
                'view_mode': 'form',
                'target': 'current',
            }
            
        except Exception as e:
            raise exceptions.UserError(f"Import failed: {str(e)}")

    def action_export(self):
        """Execute export operation"""
        if not self.model_name:
            raise exceptions.UserError("Please specify the source model.")
        
        # Check if source model exists
        try:
            self.env[self.model_name]
        except KeyError:
            raise exceptions.UserError(f"Model '{self.model_name}' does not exist.")
        
        # Create operation record
        operation = self.env['unified.file.format'].create({
            'name': f"Export {self.model_name} to CSV",
            'operation_type': 'export',
            'model_name': self.model_name,
            'file_format': 'csv',
            'domain_filter': self.domain_filter,
            'field_list': self.field_list,
            'state': 'draft'
        })
        
        # Perform export
        try:
            operation.perform_export(
                self.model_name,
                'csv',
                self.domain_filter,
                self.field_list
            )
            
            return {
                'type': 'ir.actions.act_window',
                'name': 'Export Result',
                'res_model': 'unified.file.format',
                'res_id': operation.id,
                'view_mode': 'form',
                'target': 'current',
            }
            
        except Exception as e:
            raise exceptions.UserError(f"Export failed: {str(e)}")