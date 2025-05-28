# wizards/unified_file_import_wizard.py
from odoo import models, fields, api
from odoo.exceptions import UserError
import base64
import logging

_logger = logging.getLogger(__name__)

class UnifiedFileImportWizard(models.TransientModel):
    _name = 'unified.file.import.wizard'
    _description = 'Quick Import Wizard for Unified File'

    name = fields.Char('Import Name', required=True, default=lambda self: self._default_name())
    file_data = fields.Binary('Unified File', required=True)
    file_name = fields.Char('File Name')
    
    # Import options
    create_new_company = fields.Boolean('Create New Company', default=True)
    import_accounts = fields.Boolean('Import Chart of Accounts', default=True)
    import_partners = fields.Boolean('Import Partners', default=True)
    import_products = fields.Boolean('Import Products', default=True)
    import_entries = fields.Boolean('Import Journal Entries', default=True)
    import_opening_balances = fields.Boolean('Import Opening Balances', default=True)

    def _default_name(self):
        return f'Quick Import {fields.Datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'

    def action_import(self):
        """Execute the import process"""
        self.ensure_one()
        
        if not self.file_data:
            raise UserError("Please upload a file first")
        
        # Create a full import record
        import_record = self.env['unified.file.import'].create({
            'name': self.name,
            'file_data': self.file_data,
            'file_name': self.file_name,
            'create_new_company': self.create_new_company,
            'import_accounts': self.import_accounts,
            'import_partners': self.import_partners,
            'import_products': self.import_products,
            'import_entries': self.import_entries,
            'import_opening_balances': self.import_opening_balances,
        })
        
        # Analyze the file first
        import_record.action_analyze_file()
        
        # Then import the data
        import_record.action_import_data()
        
        # Return action to view the created import record
        return {
            'name': 'Import Complete',
            'type': 'ir.actions.act_window',
            'res_model': 'unified.file.import',
            'res_id': import_record.id,
            'view_mode': 'form',
            'target': 'current',
        }


# Additional parser improvements
# models/unified_file_parser.py (extended version)

class UnifiedFileParserExtended(models.Model):
    _inherit = 'unified.file.parser'

    def _parse_advanced_format(self, file_content):
        """Parse more complex unified file formats"""
        result = {
            'company_name': '',
            'company_vat': '',
            'company_address': '',
            'accounts': [],
            'partners': [],
            'products': [],
            'journal_entries': [],
            'opening_balances': [],
        }
        
        # Handle different file encodings
        try:
            if isinstance(file_content, bytes):
                # Try different encodings
                for encoding in ['utf-8', 'windows-1255', 'iso-8859-8']:
                    try:
                        file_content = file_content.decode(encoding)
                        break
                    except UnicodeDecodeError:
                        continue
                else:
                    raise UserError("Could not decode file. Please check file encoding.")
        except Exception as e:
            _logger.error(f"Error decoding file: {e}")
            raise UserError(f"Error reading file: {e}")
        
        # Parse different formats
        if self._is_xml_format(file_content):
            return self._parse_xml_format(file_content)
        elif self._is_csv_format(file_content):
            return self._parse_csv_format(file_content)
        elif self._is_fixed_width_format(file_content):
            return self._parse_fixed_width_format(file_content)
        else:
            return self._parse_delimited_format(file_content)

    def _is_xml_format(self, content):
        """Check if file is XML format"""
        return content.strip().startswith('<?xml') or '<' in content[:100]

    def _is_csv_format(self, content):
        """Check if file is CSV format"""
        first_lines = content.split('\n')[:5]
        return any(',' in line and line.count(',') > 2 for line in first_lines)

    def _is_fixed_width_format(self, content):
        """Check if file is fixed width format"""
        lines = content.split('\n')[:10]
        if len(lines) < 2:
            return False
        
        # Check if lines have consistent length
        lengths = [len(line) for line in lines if line.strip()]
        return len(set(lengths)) <= 2  # Allow for some variation

    def _parse_xml_format(self, content):
        """Parse XML unified file format"""
        import xml.etree.ElementTree as ET
        
        try:
            root = ET.fromstring(content)
            result = {
                'company_name': '',
                'company_vat': '',
                'company_address': '',
                'accounts': [],
                'partners': [],
                'products': [],
                'journal_entries': [],
                'opening_balances': [],
            }
            
            # Parse company info
            company_elem = root.find('.//Company')
            if company_elem is not None:
                result['company_name'] = company_elem.findtext('Name', '')
                result['company_vat'] = company_elem.findtext('VAT', '')
                result['company_address'] = company_elem.findtext('Address', '')
            
            # Parse accounts
            for account_elem in root.findall('.//Account'):
                result['accounts'].append({
                    'code': account_elem.findtext('Code', ''),
                    'name': account_elem.findtext('Name', ''),
                    'type': account_elem.findtext('Type', 'asset').lower()
                })
            
            # Parse partners
            for partner_elem in root.findall('.//Partner'):
                partner_type = partner_elem.get('type', 'customer')
                result['partners'].append({
                    'name': partner_elem.findtext('Name', ''),
                    'vat': partner_elem.findtext('VAT', ''),
                    'phone': partner_elem.findtext('Phone', ''),
                    'email': partner_elem.findtext('Email', ''),
                    'address': partner_elem.findtext('Address', ''),
                    'type': partner_type,
                    'is_company': True
                })
            
            return result
            
        except ET.ParseError as e:
            raise UserError(f"Error parsing XML file: {e}")

    def _parse_csv_format(self, content):
        """Parse CSV unified file format"""
        import csv
        import io
        
        result = {
            'company_name': '',
            'company_vat': '',
            'company_address': '',
            'accounts': [],
            'partners': [],
            'products': [],
            'journal_entries': [],
            'opening_balances': [],
        }
        
        try:
            # Try different delimiters
            for delimiter in [',', ';', '\t', '|']:
                content_io = io.StringIO(content)
                reader = csv.reader(content_io, delimiter=delimiter)
                
                rows = []
                for row in reader:
                    if len(row) > 1:  # Valid row
                        rows.append(row)
                
                if len(rows) > 0:
                    # Found valid format
                    return self._process_csv_rows(rows, result)
            
            raise UserError("Could not parse CSV file with any common delimiter")
            
        except Exception as e:
            raise UserError(f"Error parsing CSV file: {e}")

    def _process_csv_rows(self, rows, result):
        """Process CSV rows and extract data"""
        current_section = None
        
        for row in rows:
            if not row or not row[0]:
                continue
            
            # Check for section headers
            first_cell = row[0].upper().strip()
            if first_cell in ['COMPANY', 'חברה']:
                current_section = 'company'
                continue
            elif first_cell in ['ACCOUNTS', 'חשבונות']:
                current_section = 'accounts'
                continue
            elif first_cell in ['CUSTOMERS', 'לקוחות']:
                current_section = 'customers'
                continue
            elif first_cell in ['SUPPLIERS', 'ספקים']:
                current_section = 'suppliers'
                continue
            elif first_cell in ['ITEMS', 'פריטים']:
                current_section = 'items'
                continue
            
            # Process data rows
            if current_section == 'company' and len(row) >= 2:
                if row[0].upper() in ['NAME', 'שם']:
                    result['company_name'] = row[1]
                elif row[0].upper() in ['VAT', 'ח.פ']:
                    result['company_vat'] = row[1]
                elif row[0].upper() in ['ADDRESS', 'כתובת']:
                    result['company_address'] = row[1]
            
            elif current_section == 'accounts' and len(row) >= 3:
                result['accounts'].append({
                    'code': row[0],
                    'name': row[1],
                    'type': row[2].lower() if len(row) > 2 else 'asset'
                })
            
            elif current_section in ['customers', 'suppliers'] and len(row) >= 1:
                result['partners'].append({
                    'name': row[0],
                    'vat': row[1] if len(row) > 1 else '',
                    'phone': row[2] if len(row) > 2 else '',
                    'email': row[3] if len(row) > 3 else '',
                    'address': row[4] if len(row) > 4 else '',
                    'type': current_section.rstrip('s'),
                    'is_company': True
                })
        
        return result

    def _parse_fixed_width_format(self, content):
        """Parse fixed-width unified file format"""
        lines = content.split('\n')
        result = {
            'company_name': '',
            'company_vat': '',
            'company_address': '',
            'accounts': [],
            'partners': [],
            'products': [],
            'journal_entries': [],
            'opening_balances': [],
        }
        
        current_section = None
        
        for line in lines:
            if not line.strip():
                continue
            
            # Identify sections by line patterns
            if line.startswith('COMP') or line.startswith('חברה'):
                current_section = 'company'
                result['company_name'] = line[10:50].strip()
                result['company_vat'] = line[50:65].strip()
                continue
            elif line.startswith('ACCT') or line.startswith('חשב'):
                current_section = 'accounts'
                if len(line) >= 50:
                    result['accounts'].append({
                        'code': line[4:14].strip(),
                        'name': line[14:50].strip(),
                        'type': 'asset'
                    })
            elif line.startswith('CUST') or line.startswith('לקוח'):
                current_section = 'customers'
                if len(line) >= 50:
                    result['partners'].append({
                        'name': line[4:40].strip(),
                        'vat': line[40:55].strip(),
                        'type': 'customer',
                        'is_company': True
                    })
            elif line.startswith('SUPP') or line.startswith('ספק'):
                current_section = 'suppliers'
                if len(line) >= 50:
                    result['partners'].append({
                        'name': line[4:40].strip(),
                        'vat': line[40:55].strip(),
                        'type': 'supplier',
                        'is_company': True
                    })
        
        return result

    def _parse_delimited_format(self, content):
        """Parse pipe-delimited or other delimited formats"""
        lines = content.split('\n')
        result = {
            'company_name': '',
            'company_vat': '',
            'company_address': '',
            'accounts': [],
            'partners': [],
            'products': [],
            'journal_entries': [],
            'opening_balances': [],
        }
        
        current_section = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Try different delimiters
            delimiter = '|'
            if '|' not in line and '\t' in line:
                delimiter = '\t'
            elif '|' not in line and ';' in line:
                delimiter = ';'
            
            # Identify section headers
            if line.startswith('*') or line.upper().startswith('SECTION'):
                if 'COMPANY' in line.upper() or 'חברה' in line:
                    current_section = 'company'
                elif 'ACCOUNT' in line.upper() or 'חשבונות' in line:
                    current_section = 'accounts'
                elif 'CUSTOMER' in line.upper() or 'לקוחות' in line:
                    current_section = 'customers'
                elif 'SUPPLIER' in line.upper() or 'ספקים' in line:
                    current_section = 'suppliers'
                elif 'ITEM' in line.upper() or 'פריטים' in line:
                    current_section = 'items'
                elif 'BALANCE' in line.upper() or 'יתרות' in line:
                    current_section = 'balances'
                continue
            
            # Parse data lines
            parts = line.split(delimiter)
            
            if current_section == 'company' and len(parts) >= 2:
                field_name = parts[0].upper().strip()
                if field_name in ['NAME', 'שם']:
                    result['company_name'] = parts[1].strip()
                elif field_name in ['VAT', 'ח.פ']:
                    result['company_vat'] = parts[1].strip()
                elif field_name in ['ADDRESS', 'כתובת']:
                    result['company_address'] = parts[1].strip()
            
            elif current_section == 'accounts' and len(parts) >= 3:
                result['accounts'].append({
                    'code': parts[0].strip(),
                    'name': parts[1].strip(),
                    'type': parts[2].strip().lower() if len(parts) > 2 else 'asset'
                })
            
            elif current_section in ['customers', 'suppliers'] and len(parts) >= 1:
                result['partners'].append({
                    'name': parts[0].strip(),
                    'vat': parts[1].strip() if len(parts) > 1 else '',
                    'phone': parts[2].strip() if len(parts) > 2 else '',
                    'email': parts[3].strip() if len(parts) > 3 else '',
                    'address': parts[4].strip() if len(parts) > 4 else '',
                    'type': current_section.rstrip('s'),
                    'is_company': True
                })
            
            elif current_section == 'items' and len(parts) >= 2:
                result['products'].append({
                    'code': parts[0].strip(),
                    'name': parts[1].strip(),
                    'price': float(parts[2].strip()) if len(parts) > 2 and parts[2].strip() else 0.0,
                    'cost': float(parts[3].strip()) if len(parts) > 3 and parts[3].strip() else 0.0
                })
            
            elif current_section == 'balances' and len(parts) >= 2:
                try:
                    balance = float(parts[1].strip()) if parts[1].strip() else 0.0
                    result['opening_balances'].append({
                        'account_code': parts[0].strip(),
                        'balance': balance
                    })
                except ValueError:
                    continue  # Skip invalid balance lines
        
        return result

    def parse_file(self):
        """Enhanced parse_file method with better format detection"""
        if not self.file_data:
            raise UserError("No file data provided")
        
        try:
            # Decode the file
            file_content = base64.b64decode(self.file_data)
            
            # Use the advanced parser
            result = self._parse_advanced_format(file_content)
            
            # Validate and clean the results
            result = self._validate_and_clean_data(result)
            
            # Update counts
            result['accounts_count'] = len(result['accounts'])
            result['partners_count'] = len(result['partners'])
            result['products_count'] = len(result['products'])
            result['entries_count'] = len(result['journal_entries'])
            
            return result
            
        except Exception as e:
            _logger.error(f"Error parsing file {self.file_name}: {e}")
            raise UserError(f"Error parsing file: {e}")

    def _validate_and_clean_data(self, data):
        """Validate and clean parsed data"""
        # Clean company data
        if not data.get('company_name'):
            data['company_name'] = 'Imported Company'
        
        # Validate VAT format for Israel
        if data.get('company_vat'):
            vat = re.sub(r'\D', '', data['company_vat'])  # Keep only digits
            if len(vat) != 9:
                _logger.warning(f"Invalid VAT format: {data['company_vat']}")
        
        # Validate account codes
        seen_codes = set()
        valid_accounts = []
        for account in data.get('accounts', []):
            if account.get('code') and account.get('name'):
                if account['code'] not in seen_codes:
                    seen_codes.add(account['code'])
                    valid_accounts.append(account)
        data['accounts'] = valid_accounts
        
        # Validate partners
        valid_partners = []
        for partner in data.get('partners', []):
            if partner.get('name'):
                valid_partners.append(partner)
        data['partners'] = valid_partners
        
        # Validate products
        valid_products = []
        for product in data.get('products', []):
            if product.get('name'):
                valid_products.append(product)
        data['products'] = valid_products
        
        return data