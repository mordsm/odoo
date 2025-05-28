# models/unified_file_parser.py
class UnifiedFileParser(models.Model):
    _name = 'unified.file.parser'
    _description = 'Parser for Unified File Format'

    file_data = fields.Binary('File Data', required=True)
    file_name = fields.Char('File Name')

    def parse_file(self):
        """Parse the unified file and extract all data"""
        if not self.file_data:
            raise UserError("No file data provided")
        
        # Decode the file
        file_content = base64.b64decode(self.file_data).decode('utf-8')
        
        # Initialize result structure
        result = {
            'company_name': '',
            'company_vat': '',
            'company_address': '',
            'accounts': [],
            'partners': [],
            'products': [],
            'journal_entries': [],
            'opening_balances': [],
            'accounts_count': 0,
            'partners_count': 0,
            'products_count': 0,
            'entries_count': 0,
        }
        
        # Parse line by line
        lines = file_content.split('\n')
        current_section = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Identify section headers
            if line.startswith('*COMPANY*'):
                current_section = 'company'
                continue
            elif line.startswith('*ACCOUNTS*'):
                current_section = 'accounts'
                continue
            elif line.startswith('*CUSTOMERS*'):
                current_section = 'customers'
                continue
            elif line.startswith('*SUPPLIERS*'):
                current_section = 'suppliers'
                continue
            elif line.startswith('*ITEMS*'):
                current_section = 'items'
                continue
            elif line.startswith('*TRANSACTIONS*'):
                current_section = 'transactions'
                continue
            elif line.startswith('*BALANCES*'):
                current_section = 'balances'
                continue
            
            # Parse data based on current section
            if current_section == 'company':
                self._parse_company_line(line, result)
            elif current_section == 'accounts':
                self._parse_account_line(line, result)
            elif current_section in ['customers', 'suppliers']:
                self._parse_partner_line(line, result, current_section)
            elif current_section == 'items':
                self._parse_product_line(line, result)
            elif current_section == 'transactions':
                self._parse_transaction_line(line, result)
            elif current_section == 'balances':
                self._parse_balance_line(line, result)
        
        # Update counts
        result['accounts_count'] = len(result['accounts'])
        result['partners_count'] = len(result['partners'])
        result['products_count'] = len(result['products'])
        result['entries_count'] = len(result['journal_entries'])
        
        return result

    def _parse_company_line(self, line, result):
        """Parse company information line"""
        # Example format: FIELD_NAME|VALUE
        if '|' in line:
            field, value = line.split('|', 1)
            if field == 'NAME':
                result['company_name'] = value
            elif field == 'VAT':
                result['company_vat'] = value
            elif field == 'ADDRESS':
                result['company_address'] = value

    def _parse_account_line(self, line, result):
        """Parse chart of accounts line"""
        # Example format: CODE|NAME|TYPE
        parts = line.split('|')
        if len(parts) >= 3:
            result['accounts'].append({
                'code': parts[0],
                'name': parts[1],
                'type': parts[2].lower() if len(parts) > 2 else 'asset'
            })

    def _parse_partner_line(self, line, result, partner_type):
        """Parse customer/supplier line"""
        # Example format: NAME|VAT|PHONE|EMAIL|ADDRESS
        parts = line.split('|')
        if len(parts) >= 1:
            result['partners'].append({
                'name': parts[0],
                'vat': parts[1] if len(parts) > 1 else '',
                'phone': parts[2] if len(parts) > 2 else '',
                'email': parts[3] if len(parts) > 3 else '',
                'address': parts[4] if len(parts) > 4 else '',
                'type': partner_type.rstrip('s'),  # 'customers' -> 'customer'
                'is_company': True
            })

    def _parse_product_line(self, line, result):
        """Parse product/item line"""
        # Example format: CODE|NAME|PRICE|COST
        parts = line.split('|')
        if len(parts) >= 2:
            result['products'].append({
                'code': parts[0],
                'name': parts[1],
                'price': float(parts[2]) if len(parts) > 2 and parts[2] else 0.0,
                'cost': float(parts[3]) if len(parts) > 3 and parts[3] else 0.0
            })

    def _parse_transaction_line(self, line, result):
        """Parse transaction line"""
        # This would depend on the specific format of your unified file
        # Example implementation for a basic format
        pass

    def _parse_balance_line(self, line, result):
        """Parse opening balance line"""
        # Example format: ACCOUNT_CODE|BALANCE
        parts = line.split('|')
        if len(parts) >= 2:
            result['opening_balances'].append({
                'account_code': parts[0],
                'balance': float(parts[1]) if parts[1] else 0.0
            })