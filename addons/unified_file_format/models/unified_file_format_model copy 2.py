from odoo import models, fields, api, exceptions
import base64
import csv
import logging
from pathlib import Path 

_logger = logging.getLogger(__name__)

class FileFormatModel(models.Model):
    _name = 'unified.file.format'
    _description = 'Unified File Format Operations'
    _order = 'create_date desc'

    name = fields.Char('Operation Name', required=True)
    operation_type = fields.Selection([
        ('import', 'Import'),
        ('export', 'Export')
    ], string='Operation Type', required=True)
    
    model_name = fields.Char('Target Model', required=True)
    file_name = fields.Char('File Name')
    file_data = fields.Binary('File Data')
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('done', 'Done'),
        ('error', 'Error')
    ], string='State', default='draft')
    
    result_message = fields.Text('Result Message')
    records_processed = fields.Integer('Records Processed')
    records_created = fields.Integer('Records Created')
    error_count = fields.Integer('Error Count')

    def perform_csv_import(self):
        """Import CSV data to target model"""
        if not self.file_data:
            raise exceptions.UserError("Please upload a CSV file first")
        
        try:
            # Decode CSV
            csv_content = base64.b64decode(self.file_data).decode('utf-8')
            csv_reader = csv.DictReader(csv_content.splitlines())
            records = list(csv_reader)
            
            if not records:
                raise exceptions.UserError("No data found in CSV file")
            
            # Import to target model
            target_model = self.env[self.model_name]
            created_count = 0
            
            for record_data in records:
                clean_data = {k: v for k, v in record_data.items() if v and str(v).strip()}
                if clean_data:
                    target_model.create(clean_data)
                    created_count += 1
            
            # Update operation status
            self.write({
                'state': 'done',
                'records_created': created_count,
                'result_message': f"Successfully imported {created_count} records to {self.model_name}"
            })
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Import Successful',
                    'message': f'Imported {created_count} records',
                    'type': 'success',
                }
            }
            
        except Exception as e:
            self.write({
                'state': 'error',
                'result_message': f"Import failed: {str(e)}"
            })
            raise exceptions.UserError(f"Import failed: {str(e)}")
    def perform_csv_export(self):
        """Method called by the Export CSV button"""
        # Your CSV export logic here
        pass
    def perform_unified_import(self):
        """Import file using unified file format system"""
        if not self.file_data:
            raise exceptions.UserError("Please upload a file first")
        
        try:
            # Check if this is a fixed-width format file
            file_content_preview = base64.b64decode(self.file_data).decode('utf-8', errors='ignore')[:200]
            
            if file_content_preview.startswith('A') and 'B' in file_content_preview:
                # This looks like your fixed-width format
                return self.perform_fixed_width_import()
            
            # Otherwise, use standard unified file format
            file_extension = Path(self.file_name or '').suffix.lower()
            
            if file_extension == '.csv':
                return self.perform_csv_import()  # Your existing CSV method
            else:
                # Default to fixed-width parser for your format
                return self.perform_fixed_width_import()
                
        except Exception as e:
            self.write({
                'state': 'error',
                'result_message': f"Import failed: {str(e)}"
            })
            raise exceptions.UserError(f"Import failed: {str(e)}")
    def perform_fixed_width_import(self):
        """Import fixed-width format file with proper Hebrew encoding and debug logging"""
        if not self.file_data:
            raise exceptions.UserError("Please upload a file first")
        
        try:
            # Try different encodings for Hebrew files
            file_content = None
            encodings_to_try = ['windows-1255', 'cp1255', 'iso-8859-8', 'utf-8']
            
            for encoding in encodings_to_try:
                try:
                    file_content = base64.b64decode(self.file_data).decode(encoding)
                    _logger.info(f"Successfully decoded file using {encoding} encoding")
                    break
                except UnicodeDecodeError:
                    continue
            
            if file_content is None:
                # Last resort - ignore errors
                file_content = base64.b64decode(self.file_data).decode('utf-8', errors='ignore')
                _logger.warning("Used UTF-8 with errors ignored for file decoding")
            
            lines = file_content.splitlines()
            _logger.info(f"File contains {len(lines)} lines")
            
            # Parse the file
            header_info = {}
            detail_records = []
            
            # Debug counters
            individual_count = 0
            bank_count = 0
            error_count = 0
            skipped_count = 0
            
            for line_num, line in enumerate(lines, 1):
                line = line.strip()
                if not line:  # Skip empty lines
                    continue
                    
                try:
                    if line.startswith('A'):
                        header_info = self._parse_header_record(line)
                        _logger.info(f"Parsed header: {header_info}")
                    elif line.startswith('B'):
                        # Debug: check what type is detected BEFORE parsing
                        detected_type = self._detect_b_record_type(line)
                        
                        detail_record = self._parse_detail_record(line)
                        if detail_record and not detail_record.get('parse_error'):
                            detail_record['line_number'] = line_num
                            detail_records.append(detail_record)
                            
                            # Count and log by type
                            subtype = detail_record.get('record_subtype', 'unknown')
                            if subtype == 'individual_transaction':
                                individual_count += 1
                                # Log first few individual transactions for verification
                                if individual_count <= 10:
                                    customer = detail_record.get('customer_name', 'N/A')
                                    # Use only ASCII characters in logging to avoid encoding issues
                                    safe_customer = ''.join(c if ord(c) < 128 else '?' for c in customer[:15])
                                    txn_id = detail_record.get('transaction_id', 'N/A')
                                    amount = detail_record.get('amount', 0.0)
                                    _logger.info(f"Individual #{individual_count}: ID={txn_id}, Customer={safe_customer}, Amount={amount}")
                            elif subtype == 'bank_operation':
                                bank_count += 1
                                # Log first few bank operations
                                if bank_count <= 5:
                                    desc = detail_record.get('customer_name', 'N/A')
                                    safe_desc = ''.join(c if ord(c) < 128 else '?' for c in desc[:15])
                                    amount = detail_record.get('amount', 0.0)
                                    _logger.info(f"Bank #{bank_count}: Desc={safe_desc}, Amount={amount}")
                            else:
                                error_count += 1
                                _logger.warning(f"Unknown subtype '{subtype}' on line {line_num}")
                                
                        else:
                            # Log parsing failures, especially for lines that should be individual transactions
                            error_msg = detail_record.get('parse_error', 'Unknown error') if detail_record else 'Failed to parse'
                            if any(keyword in line.lower() for keyword in ['nielsen', 'perfectomobile', 'גאון']):
                                _logger.warning(f"FAILED to parse individual transaction on line {line_num}: {error_msg}")
                                _logger.warning(f"Detected type was: {detected_type}")
                                _logger.warning(f"Line preview: '{line[:100]}...'")
                            error_count += 1
                    else:
                        skipped_count += 1
                        if skipped_count <= 5:  # Log first few skipped lines
                            _logger.debug(f"Skipping line {line_num} with type: {line[0] if line else 'empty'}")
                except Exception as e:
                    error_count += 1
                    _logger.error(f"Exception parsing line {line_num}: {str(e)}")
                    continue
            
            # Log parsing summary
            _logger.info(f"=== PARSING SUMMARY ===")
            _logger.info(f"Total lines processed: {len(lines)}")
            _logger.info(f"Individual transactions found: {individual_count}")
            _logger.info(f"Bank operations found: {bank_count}")
            _logger.info(f"Parse errors: {error_count}")
            _logger.info(f"Valid detail records: {len(detail_records)}")
            
            # Validate we have records to process
            if not detail_records:
                raise exceptions.UserError("No valid B records found in the file. Please check file format.")
            
            # Import records to target model
            try:
                target_model = self.env[self.model_name]
            except KeyError:
                raise exceptions.UserError(f"Target model '{self.model_name}' does not exist. Please check model name.")
            
            created_count = 0
            error_list = []
            individual_created = 0
            bank_created = 0
            
            for record_data in detail_records:
                try:
                    # Clean and prepare data for Odoo
                    clean_data = self._prepare_odoo_data(record_data)
                    if clean_data:
                        new_record = target_model.create(clean_data)
                        created_count += 1
                        
                        # Count by type
                        if record_data.get('record_subtype') == 'individual_transaction':
                            individual_created += 1
                            if individual_created <= 5:
                                name = clean_data.get('name', 'Unknown')[:20]
                                ref = clean_data.get('reference', 'No ref')
                                amount = clean_data.get('amount', 0.0)
                                _logger.info(f"Created individual record: {name}, Ref: {ref}, Amount: {amount}")
                        else:
                            bank_created += 1
                            
                    else:
                        warning_msg = f"Line {record_data.get('line_number', '?')}: No valid data after preparation"
                        error_list.append(warning_msg)
                        if len(error_list) <= 10:  # Log first 10 preparation failures
                            _logger.warning(warning_msg)
                except Exception as e:
                    error_msg = f"Line {record_data.get('line_number', '?')}: {str(e)}"
                    error_list.append(error_msg)
                    if len(error_list) <= 10:  # Log first 10 creation failures
                        _logger.error(error_msg)
            
            # Create detailed result message
            error_summary = ""
            if error_list:
                error_summary = f"\nFirst errors: {'; '.join(error_list[:3])}"
                if len(error_list) > 3:
                    error_summary += f"\n... and {len(error_list) - 3} more errors"
            
            success_message = (
                f"Fixed-width import completed successfully!\n"
                f"• File ID: {header_info.get('file_id', 'N/A')}\n"
                f"• Total lines in file: {len(lines)}\n"
                f"• Valid B records parsed: {len(detail_records)}\n"
                f"• Records created in database: {created_count}\n"
                f"  - Individual transactions: {individual_created}\n"
                f"  - Bank operations: {bank_created}\n"
                f"• Parse errors: {len(error_list)}\n"
                f"• Parsing breakdown:\n"
                f"  - Individual transactions detected: {individual_count}\n"
                f"  - Bank operations detected: {bank_count}\n"
                f"  - Parse failures: {error_count}"
                f"{error_summary}"
            )
            
            # Log final summary
            _logger.info(f"=== IMPORT COMPLETE ===")
            _logger.info(f"Database records created: {created_count}")
            _logger.info(f"Individual transactions in DB: {individual_created}")
            _logger.info(f"Bank operations in DB: {bank_created}")
            
            # Update operation status
            self.write({
                'state': 'done',
                'records_created': created_count,
                'records_processed': len(detail_records),
                'error_count': len(error_list),
                'result_message': success_message
            })
            
            # Return success notification
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Import Completed Successfully!',
                    'message': f'Created {created_count} records ({individual_created} individual, {bank_created} bank operations)',
                    'type': 'success',
                }
            }
            
        except exceptions.UserError:
            # Re-raise UserError as-is
            raise
        except Exception as e:
            error_msg = f"Fixed-width import failed: {str(e)}"
            self.write({
                'state': 'error',
                'result_message': error_msg
            })
            _logger.error(f"Critical error in perform_fixed_width_import: {str(e)}", exc_info=True)
            raise exceptions.UserError(error_msg)   
   
   
   
    def _parse_header_record(self, line):
        """Parse header record (A record)"""
        return {
            'record_type': line[0:1],          # A
            'file_id': line[1:21],             # File identifier
            'date_created': line[21:29],       # YYYYMMDD
            'version': line[29:35],            # Version info
            # Add more fields as needed
        }

    
    def _parse_account_balance(self, line):
        """Parse account balance (בנק הפועלים, קופת מזומן, etc.)"""
        result = {}
        
        # Clean Hebrew text
        def clean_hebrew_text(text):
            if not text:
                return ""
            cleaned = text.replace('\x00', '').strip()
            return ''.join(char for char in cleaned if ord(char) >= 32)
        
        # For account balances, the Hebrew account name might be in a different position
        # We'll need to find where it actually is after running the inspection
        
        # Try different positions to find the Hebrew account name
        account_name = ""
        possible_positions = [
            line[37:87],   # Same as individual transactions
            line[50:100],  # Slightly different
            line[30:80],   # Earlier position
        ]
        
        for pos_text in possible_positions:
            clean_text = clean_hebrew_text(pos_text)
            if clean_text and any(ord(c) > 127 for c in clean_text):  # Contains Hebrew
                account_name = clean_text
                break
        
        result.update({
            'transaction_id': '',  # Account balances don't have transaction IDs
            'customer_name': account_name,
            'record_subtype': 'account_balance'
        })
        
        # Find the largest amount (account balances tend to be large)
        amounts = []
        import re
        amount_matches = re.finditer(r'[+-]\d{10,15}', line)
        for match in amount_matches:
            amount_str = match.group()
            try:
                sign = 1 if amount_str.startswith('+') else -1
                amount_digits = amount_str[1:].lstrip('0') or '0'
                if len(amount_digits) >= 2:
                    amount_value = float(amount_digits[:-2] + '.' + amount_digits[-2:])
                else:
                    amount_value = float(amount_digits) / 100
                amounts.append(sign * amount_value)
            except ValueError:
                continue
        
        # Use the largest absolute amount
        if amounts:
            result['amount'] = max(amounts, key=abs)
        else:
            result['amount'] = 0.0
        
        return result
   
    
    
    def _extract_dates_and_currency(self, line):
        """Extract dates and currency from line"""
        result = {}
        
        # Find dates (8 consecutive digits that look like dates)
        import re
        date_patterns = re.findall(r'\b(20\d{6})\b', line)  # Dates starting with 20 (2010-2099)
        
        if date_patterns:
            # Use first date as transaction date
            result['transaction_date'] = date_patterns[0]
            # If there's a second date, use it as value date
            if len(date_patterns) > 1:
                result['value_date'] = date_patterns[1]
            else:
                result['value_date'] = date_patterns[0]  # Same as transaction date
        
        # Detect currency
        currency = 'ILS'  # Default to ILS (Shekels) since most transactions are in Shekels
        
        # Look for explicit currency indicators
        if 'USD' in line.upper():
            currency = 'USD'
        elif 'ILS' in line.upper() or 'שח' in line or 'שקל' in line:
            currency = 'ILS'
        elif 'EUR' in line.upper() or 'אירו' in line:
            currency = 'EUR'
        
        # Alternative method: check amount area for currency codes
        # Individual transactions: check position 200-220
        if len(line) > 220:
            currency_area = line[200:220].upper()
            if 'USD' in currency_area:
                currency = 'USD'
            elif 'EUR' in currency_area:
                currency = 'EUR'
            # If no explicit currency found, default to ILS
        
        result['currency'] = currency
        return result

    def _parse_individual_transaction(self, line):
        """Parse individual customer transaction with dates and proper currency"""
        result = {}
        
        def clean_hebrew_text(text):
            if not text:
                return ""
            cleaned = text.replace('\x00', '').strip()
            return ''.join(char for char in cleaned if ord(char) >= 32)
        
        # Extract dates and currency
        date_currency_info = self._extract_dates_and_currency(line)
        
        # EXACT POSITIONS from previous analysis
        result.update({
            'transaction_id': line[21:28].strip(),
            'customer_name': clean_hebrew_text(line[37:67]),
            'amount2': line[292:307].strip(),
            'record_subtype': 'individual_transaction',
            # Add date and currency info
            'transaction_date': date_currency_info.get('transaction_date', ''),
            'value_date': date_currency_info.get('value_date', ''),
            'currency': date_currency_info.get('currency', 'ILS')
        })
        
        # Validate transaction_id
        if not result['transaction_id'] or len(result['transaction_id']) < 6:
            import re
            matches = re.findall(r'\b92\d{5}\b', line)
            if matches:
                result['transaction_id'] = matches[0]
        
        # Validate customer_name
        if not result['customer_name'] or len(result['customer_name']) < 3:
            result['parse_error'] = f"Invalid customer name: '{result['customer_name'][:20]}'"
            return result
        
        # Convert amount
        amount_str = result['amount2']
        if amount_str and amount_str.startswith(('+', '-')):
            try:
                sign = 1 if amount_str.startswith('+') else -1
                amount_digits = amount_str[1:].lstrip('0') or '0'
                if len(amount_digits) >= 2:
                    amount_value = float(amount_digits[:-2] + '.' + amount_digits[-2:])
                else:
                    amount_value = float(amount_digits) / 100
                result['amount'] = sign * amount_value
            except ValueError:
                result['amount'] = 0.0
        else:
            result['amount'] = 0.0
        
        # Final validation
        if result['amount'] == 0.0:
            result['parse_error'] = f"Zero or invalid amount: '{amount_str}'"
            return result
        
        return result

    def _parse_bank_operation(self, line):
        """Parse bank operation with dates and proper currency"""
        result = {}
        
        def clean_hebrew_text(text):
            if not text:
                return ""
            cleaned = text.replace('\x00', '').strip()
            return ''.join(char for char in cleaned if ord(char) >= 32)
        
        # Extract dates and currency
        date_currency_info = self._extract_dates_and_currency(line)
        
        # Bank operations fields
        result.update({
            'transaction_id': '',  # Bank operations don't have customer transaction IDs
            'customer_name': clean_hebrew_text(line[100:140]),  # Extended range for descriptions
            'record_subtype': 'bank_operation',
            # Add date and currency info
            'transaction_date': date_currency_info.get('transaction_date', ''),
            'value_date': date_currency_info.get('value_date', ''),
            'currency': date_currency_info.get('currency', 'ILS')
        })
        
        # Extract amount from position 200-220
        amount_area = line[200:220] if len(line) > 220 else ''
        result['amount'] = 0.0
        
        if amount_area:
            import re
            # Look for amount patterns: 1USD+0000000007375, 1ILS+0000000007375, etc.
            amount_match = re.search(r'(USD|ILS|EUR)?\+?(\d+)', amount_area)
            if amount_match:
                currency_code = amount_match.group(1)
                amount_digits = amount_match.group(2).lstrip('0') or '0'
                
                # Update currency if found in amount area
                if currency_code:
                    result['currency'] = currency_code
                    
                try:
                    if len(amount_digits) >= 2:
                        amount_value = float(amount_digits[:-2] + '.' + amount_digits[-2:])
                    else:
                        amount_value = float(amount_digits) / 100
                    result['amount'] = amount_value
                except ValueError:
                    result['amount'] = 0.0
        
        return result

    def _prepare_odoo_data(self, record_data):
        """Prepare data with dates and correct currency"""
        if record_data.get('parse_error'):
            return None
        
        # Get fields from parsed data
        customer_name = record_data.get('customer_name', '').strip()
        transaction_id = record_data.get('transaction_id', '').strip()
        record_subtype = record_data.get('record_subtype', 'unknown')
        amount = record_data.get('amount', 0.0)
        currency = record_data.get('currency', 'ILS')  # Default to ILS instead of USD
        
        # Create description
        if record_subtype == 'individual_transaction':
            if customer_name:
                description = customer_name
            elif transaction_id:
                description = f"Customer Transaction {transaction_id}"
            else:
                description = "Individual Transaction"
        else:
            description = customer_name if customer_name else "Bank Operation"
        
        # Build clean data
        clean_data = {
            'name': description[:100],
            'amount': amount,
            'currency': currency,  # Use detected currency
            'transaction_code': record_subtype,
        }
        
        # Add optional fields
        if transaction_id:
            clean_data['reference'] = transaction_id
        
        if record_data.get('file_id'):
            clean_data['sequence'] = record_data['file_id']
        
        if record_data.get('account_number') and record_data['account_number'] != '0' * len(record_data['account_number']):
            clean_data['account_number'] = record_data['account_number']
        
        # Add raw data (truncated)
        if record_data.get('raw_line'):
            clean_data['raw_line'] = record_data['raw_line'][:500]
        
        # DATE handling - convert YYYYMMDD to YYYY-MM-DD
        transaction_date = record_data.get('transaction_date', '')
        if len(transaction_date) == 8 and transaction_date.isdigit():
            try:
                year = transaction_date[0:4]
                month = transaction_date[4:6]
                day = transaction_date[6:8]
                # Validate date components
                if 1 <= int(month) <= 12 and 1 <= int(day) <= 31 and int(year) >= 2000:
                    clean_data['transaction_date'] = f"{year}-{month}-{day}"
            except (ValueError, IndexError):
                pass  # Skip invalid dates
        
        # VALUE DATE handling
        value_date = record_data.get('value_date', '')
        if len(value_date) == 8 and value_date.isdigit() and value_date != transaction_date:
            try:
                year = value_date[0:4]
                month = value_date[4:6]
                day = value_date[6:8]
                if 1 <= int(month) <= 12 and 1 <= int(day) <= 31 and int(year) >= 2000:
                    clean_data['value_date'] = f"{year}-{month}-{day}"
            except (ValueError, IndexError):
                pass
        
        # Validation
        if not clean_data.get('name') or len(clean_data['name']) < 1:
            return None
        
        # Don't reject zero amounts for bank operations
        if record_subtype == 'individual_transaction' and amount == 0.0:
            return None
        
        return clean_data


    
    
    
    def _detect_b_record_type(self, line):
        """CORRECTED detection - prioritize individual transactions"""
        
        def clean_hebrew_text(text):
            if not text:
                return ""
            cleaned = text.replace('\x00', '').strip()
            return ''.join(char for char in cleaned if ord(char) >= 32)
        
        # METHOD 1: Check for exact transaction ID patterns at position 21 (HIGHEST PRIORITY)
        if len(line) > 28:
            txn_id_area = line[21:28].strip()
            if txn_id_area.startswith('92') and txn_id_area.isdigit() and len(txn_id_area) == 7:
                # This matches 9200035, 9200036, etc. - definitely individual transaction
                return "individual_transaction"
        
        # METHOD 2: Check for specific customer names at position 37 (from Image 5)
        if len(line) > 67:
            name_area = clean_hebrew_text(line[37:67]).lower()
            individual_names = ['nielsen', 'perfectomobile', 'גאון', 'אחזקות']
            for name in individual_names:
                if name in name_area:
                    return "individual_transaction"
        
        # METHOD 3: Check for English text in customer name area (individual customers often have English names)
        if len(line) > 67:
            name_area = line[37:67].strip()
            # Look for English letters (non-Hebrew, non-digits)
            if any(c.isalpha() and ord(c) < 128 for c in name_area):
                return "individual_transaction"
        
        # METHOD 4: Check for specific amount patterns that indicate individual transactions
        if len(line) > 307:
            # Individual transactions have significant amounts at position 292-307
            amount_area = line[292:307]
            if amount_area.startswith(('+', '-')) and amount_area[1:].isdigit():
                # Check if this is a substantial amount (not tiny bank fees)
                try:
                    amount_digits = amount_area[1:].lstrip('0')
                    if len(amount_digits) >= 6:  # Amounts like 645840, 2065518 (substantial amounts)
                        return "individual_transaction"
                except:
                    pass
        
        # DEFAULT: Bank operation
        return "bank_operation"

    
    def _parse_detail_record(self, line):
        """Parse detail record with dates and currency detection"""
        result = {
            'record_type': line[0:1] if len(line) > 0 else '',
            'raw_line': line,
            'parse_error': None
        }
        
        try:
            if not line.startswith('B') or len(line) < 200:
                result['parse_error'] = f'Invalid B record'
                return result
            
            # Extract basic fields for all records
            result['file_id'] = line[20:40].strip()
            result['account_number'] = line[60:80].strip()
            
            # DETECT RECORD TYPE
            record_type = self._detect_b_record_type(line)
            
            if record_type == "individual_transaction":
                individual_result = self._parse_individual_transaction(line)
                if individual_result.get('parse_error'):
                    result.update(self._parse_bank_operation(line))
                else:
                    result.update(individual_result)
                    
            else:  # bank_operation
                result.update(self._parse_bank_operation(line))
            
            # Ensure currency is set (fallback to ILS)
            if not result.get('currency'):
                result['currency'] = 'ILS'
            
            # Final validation
            customer_name = result.get('customer_name', '').strip()
            if not customer_name or len(customer_name) < 2:
                result['parse_error'] = "Invalid or missing description"
                return result
                
        except Exception as e:
            result['parse_error'] = f"Parse error: {str(e)}"
        
        return result


    
    
    def action_csv_import(self):
        """Simple CSV import"""
        if not self.file_data:
            raise exceptions.UserError("No file data provided")
        
        try:
            # Decode CSV data
            csv_content = base64.b64decode(self.file_data).decode('utf-8')
            csv_reader = csv.DictReader(csv_content.splitlines())
            records = list(csv_reader)
            
            if not records:
                raise exceptions.UserError("No data found in CSV")
            
            # Get target model
            target_model = self.env[self.model_name]
            created_count = 0
            error_count = 0
            
            for record_data in records:
                try:
                    # Clean data
                    clean_data = {k: v for k, v in record_data.items() if v and v.strip()}
                    target_model.create(clean_data)
                    created_count += 1
                except Exception as e:
                    error_count += 1
                    _logger.warning(f"Failed to create record: {e}")
            
            # Update operation
            self.write({
                'state': 'done',
                'records_processed': len(records),
                'records_created': created_count,
                'error_count': error_count,
                'result_message': f"Import completed: {created_count} created, {error_count} errors"
            })
            
        except Exception as e:
            self.write({
                'state': 'error',
                'result_message': f"Import failed: {str(e)}"
            })
            raise exceptions.UserError(f"Import failed: {str(e)}")

    def action_csv_export(self):
            """Simple CSV export"""
            try:
                # Get source model
                source_model = self.env[self.model_name]
                records = source_model.search([])
                
                if not records:
                    raise exceptions.UserError("No records found")
                
                # Get basic fields
                field_list = ['id', 'name']
                if 'email' in source_model._fields:
                    field_list.append('email')
                if 'phone' in source_model._fields:
                    field_list.append('phone')
                
                # Read data
                data = records.read(field_list)
                
                # Create CSV
                import io
                output = io.StringIO()
                writer = csv.DictWriter(output, fieldnames=field_list)
                writer.writeheader()
                
                for record in data:
                    clean_record = {}
                    for key, value in record.items():
                        if isinstance(value, (list, tuple)) and len(value) == 2:
                            clean_record[key] = value[1]  # Many2one field
                        else:
                            clean_record[key] = str(value) if value else ''
                    writer.writerow(clean_record)
                
                csv_content = output.getvalue()
                output.close()
                
                # Save result
                self.write({
                    'state': 'done',
                    'file_data': base64.b64encode(csv_content.encode('utf-8')),
                    'file_name': f"{self.model_name}_export.csv",
                    'records_processed': len(data),
                    'result_message': f"Export completed: {len(data)} records"
                })
                
            except Exception as e:
                self.write({
                    'state': 'error',
                    'result_message': f"Export failed: {str(e)}"
                })
                raise exceptions.UserError(f"Export failed: {str(e)}")
    def analyze_file_structure(self):
            """Analyze the actual file structure and suggest correct field mapping"""
            if not self.file_data:
                raise exceptions.UserError("Please upload a file first")
            
            try:
                # Decode file content
                file_content = None
                encodings_to_try = ['windows-1255', 'cp1255', 'iso-8859-8', 'utf-8']
                
                for encoding in encodings_to_try:
                    try:
                        file_content = base64.b64decode(self.file_data).decode(encoding)
                        break
                    except UnicodeDecodeError:
                        continue
                
                if file_content is None:
                    file_content = base64.b64decode(self.file_data).decode('utf-8', errors='ignore')
                
                lines = file_content.splitlines()
                
                # Find B records
                b_records = [line for line in lines if line.startswith('B')][:5]  # Analyze first 5 B records
                
                if not b_records:
                    return "No B records found in file"
                
                analysis_result = []
                analysis_result.append("=== FILE STRUCTURE ANALYSIS ===\n")
                analysis_result.append(f"Total lines: {len(lines)}")
                analysis_result.append(f"B records found: {len([l for l in lines if l.startswith('B')])}")
                analysis_result.append(f"Analyzing first {len(b_records)} B records...\n")
                
                # Analyze each B record
                for i, line in enumerate(b_records):
                    analysis_result.append(f"--- B Record #{i+1} (Length: {len(line)}) ---")
                    
                    # Break line into chunks for analysis
                    chunks = []
                    pos = 0
                    chunk_size = 20
                    
                    while pos < len(line):
                        chunk = line[pos:pos+chunk_size]
                        chunks.append((pos, chunk))
                        pos += chunk_size
                    
                    # Analyze each chunk
                    for start_pos, chunk in chunks:
                        end_pos = start_pos + len(chunk)
                        
                        # Identify chunk type
                        chunk_type = self._identify_chunk_type(chunk)
                        clean_chunk = chunk.replace('\x00', '').strip()
                        
                        analysis_result.append(f"  Pos {start_pos:3}-{end_pos:3}: '{clean_chunk}' ({chunk_type})")
                    
                    analysis_result.append("")  # Empty line between records
                
                # Auto-detect field positions
                analysis_result.append("=== SUGGESTED FIELD MAPPING ===")
                suggested_mapping = self._suggest_field_mapping(b_records[0])
                
                for field_name, info in suggested_mapping.items():
                    analysis_result.append(f"{field_name}: Position {info['start']}-{info['end']} = '{info['sample']}'")
                
                # Generate corrected _parse_detail_record function
                analysis_result.append("\n=== SUGGESTED CODE FIX ===")
                analysis_result.append("Replace your _parse_detail_record with:")
                analysis_result.append(self._generate_corrected_parser(suggested_mapping))
                
                # Update result message
                full_analysis = "\n".join(analysis_result)
                self.write({
                    'result_message': full_analysis
                })
                
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'File Analysis Complete',
                        'message': 'Check Result Message for detailed analysis and suggested fixes',
                        'type': 'info',
                    }
                }
                
            except Exception as e:
                error_msg = f"Analysis failed: {str(e)}"
                self.write({'result_message': error_msg})
                raise exceptions.UserError(error_msg)

    def _identify_chunk_type(self, chunk):
        """Identify what type of data is in a chunk"""
        clean = chunk.replace('\x00', '').strip()
        
        if not clean:
            return "EMPTY"
        elif clean.isdigit() and len(clean) == 8:
            return "DATE (YYYYMMDD)"
        elif clean.isdigit() and len(clean) > 10:
            return "LONG_NUMBER (ID/ACCOUNT)"
        elif clean.startswith(('+', '-')) and clean[1:].isdigit():
            return "AMOUNT"
        elif clean.upper() in ['USD', 'ILS', 'EUR']:
            return "CURRENCY"
        elif any(ord(c) > 127 for c in clean):  # Contains non-ASCII (Hebrew)
            return "HEBREW_TEXT"
        elif clean.isalpha():
            return "TEXT"
        elif clean.isdigit():
            return "NUMBER"
        else:
            return "MIXED"

    def _suggest_field_mapping(self, sample_line):
        """Suggest correct field mapping based on actual data"""
        mapping = {}
        
        # Split line into analysis chunks
        pos = 0
        chunk_size = 20
        chunks = []
        
        while pos < len(sample_line):
            chunk = sample_line[pos:pos+chunk_size]
            chunk_type = self._identify_chunk_type(chunk)
            chunks.append({
                'start': pos,
                'end': pos + len(chunk),
                'content': chunk.replace('\x00', '').strip(),
                'type': chunk_type
            })
            pos += chunk_size
        
        # Find specific field types
        field_counter = {
            'hebrew_text': 0,
            'date': 0,
            'amount': 0,
            'long_number': 0
        }
        
        for chunk in chunks:
            if chunk['type'] == 'HEBREW_TEXT' and field_counter['hebrew_text'] == 0:
                mapping['customer_name'] = {
                    'start': chunk['start'],
                    'end': chunk['end'],
                    'sample': chunk['content']
                }
                field_counter['hebrew_text'] += 1
                
            elif chunk['type'] == 'DATE (YYYYMMDD)' and field_counter['date'] == 0:
                mapping['transaction_date'] = {
                    'start': chunk['start'],
                    'end': chunk['end'],
                    'sample': chunk['content']
                }
                field_counter['date'] += 1
                
            elif chunk['type'] == 'DATE (YYYYMMDD)' and field_counter['date'] == 1:
                mapping['value_date'] = {
                    'start': chunk['start'],
                    'end': chunk['end'],
                    'sample': chunk['content']
                }
                field_counter['date'] += 1
                
            elif chunk['type'] == 'AMOUNT' and field_counter['amount'] == 0:
                mapping['amount'] = {
                    'start': chunk['start'],
                    'end': chunk['end'],
                    'sample': chunk['content']
                }
                field_counter['amount'] += 1
                
            elif chunk['type'] == 'LONG_NUMBER (ID/ACCOUNT)' and field_counter['long_number'] == 0:
                mapping['file_id'] = {
                    'start': chunk['start'],
                    'end': chunk['end'],
                    'sample': chunk['content']
                }
                field_counter['long_number'] += 1
                
            elif chunk['type'] == 'LONG_NUMBER (ID/ACCOUNT)' and field_counter['long_number'] == 1:
                mapping['account_number'] = {
                    'start': chunk['start'],
                    'end': chunk['end'],
                    'sample': chunk['content']
                }
                field_counter['long_number'] += 1
        
        return mapping

    def _generate_corrected_parser(self, mapping):
        """Generate corrected _parse_detail_record function"""
        code_lines = []
        code_lines.append("def _parse_detail_record(self, line):")
        code_lines.append("    result = {")
        code_lines.append("        'record_type': line[0:1],")
        code_lines.append("        'raw_line': line,")
        code_lines.append("        'parse_error': None")
        code_lines.append("    }")
        code_lines.append("    ")
        code_lines.append("    try:")
        code_lines.append("        if not line.startswith('B') or len(line) < 200:")
        code_lines.append("            result['parse_error'] = f'Invalid B record'")
        code_lines.append("            return result")
        code_lines.append("        ")
        
        # Add field extractions based on detected mapping
        for field_name, info in mapping.items():
            start = info['start']
            end = info['end']
            code_lines.append(f"        result['{field_name}'] = line[{start}:{end}].strip()")
        
        # Add amount conversion if amount field found
        if 'amount' in mapping:
            code_lines.append("        ")
            code_lines.append("        # Convert amount")
            code_lines.append("        amount_str = result.get('amount', '')")
            code_lines.append("        if amount_str:")
            code_lines.append("            try:")
            code_lines.append("                sign = 1 if amount_str.startswith('+') else -1")
            code_lines.append("                amount_digits = amount_str[1:].lstrip('0') or '0'")
            code_lines.append("                if len(amount_digits) >= 2:")
            code_lines.append("                    amount_value = float(amount_digits[:-2] + '.' + amount_digits[-2:])")
            code_lines.append("                else:")
            code_lines.append("                    amount_value = float(amount_digits) / 100")
            code_lines.append("                result['amount_value'] = sign * amount_value")
            code_lines.append("            except ValueError:")
            code_lines.append("                result['amount_value'] = 0.0")
        
        code_lines.append("        ")
        code_lines.append("    except Exception as e:")
        code_lines.append("        result['parse_error'] = f'Parse error: {str(e)}'")
        code_lines.append("    ")
        code_lines.append("    return result")
        
        return "\n".join(code_lines)

    # Add this method to your class to trigger the analysis
    def action_analyze_structure(self):
            """Button action to analyze file structure"""
            return self.analyze_file_structure()
    def action_analyze_target_model(self):
        """Analyze target model fields and suggest field mapping"""
        if not self.model_name:
            raise exceptions.UserError("Please specify target model name first")
        
        try:
            # Get target model
            target_model = self.env[self.model_name]
            
            # Get all fields from target model
            model_fields = target_model._fields
            
            result = []
            result.append(f"=== TARGET MODEL ANALYSIS: {self.model_name} ===\n")
            result.append(f"Available fields ({len(model_fields)}):\n")
            
            # Categorize fields
            text_fields = []
            date_fields = []
            number_fields = []
            other_fields = []
            
            for field_name, field_obj in model_fields.items():
                field_type = field_obj.type
                field_info = f"• {field_name} ({field_type})"
                
                if hasattr(field_obj, 'string') and field_obj.string:
                    field_info += f" - '{field_obj.string}'"
                
                if field_type in ['char', 'text']:
                    text_fields.append(field_info)
                elif field_type in ['date', 'datetime']:
                    date_fields.append(field_info)
                elif field_type in ['integer', 'float', 'monetary']:
                    number_fields.append(field_info)
                else:
                    other_fields.append(field_info)
            
            # Display categorized fields
            if text_fields:
                result.append("TEXT FIELDS:")
                result.extend(text_fields[:10])  # Show first 10
                if len(text_fields) > 10:
                    result.append(f"... and {len(text_fields) - 10} more text fields")
                result.append("")
            
            if date_fields:
                result.append("DATE FIELDS:")
                result.extend(date_fields)
                result.append("")
            
            if number_fields:
                result.append("NUMBER FIELDS:")
                result.extend(number_fields)
                result.append("")
            
            # Suggest field mapping
            result.append("=== SUGGESTED FIELD MAPPING ===")
            result.append("Based on common field names, try mapping:")
            
            suggested_mapping = {
                'name': ['name', 'description', 'label', 'memo'],
                'amount': ['amount', 'total', 'price', 'value', 'sum'],
                'date': ['date', 'transaction_date', 'date_created', 'create_date'],
                'reference': ['reference', 'ref', 'number', 'invoice_number'],
                'partner': ['partner_id', 'customer_id', 'vendor_id']
            }
            
            for data_type, possible_fields in suggested_mapping.items():
                found_fields = [f for f in possible_fields if f in model_fields]
                if found_fields:
                    result.append(f"• {data_type.upper()}: Use field '{found_fields[0]}'")
                else:
                    result.append(f"• {data_type.upper()}: No suitable field found")
            
            result.append(f"\n=== RECOMMENDED _prepare_odoo_data FIX ===")
            result.append("Replace the clean_data.update() section with:")
            result.append("clean_data = {")
            
            # Generate field mapping based on available fields
            if 'name' in model_fields:
                result.append("    'name': customer_name or f'Transaction {transaction_id}',")
            if 'amount' in model_fields:
                result.append("    'amount': record_data.get('amount', 0.0),")
            elif 'total' in model_fields:
                result.append("    'total': record_data.get('amount', 0.0),")
            elif 'price' in model_fields:
                result.append("    'price': record_data.get('amount', 0.0),")
            
            if 'date' in model_fields:
                result.append("    'date': clean_data.get('transaction_date'),")
            elif 'transaction_date' in model_fields:
                result.append("    'transaction_date': clean_data.get('transaction_date'),")
            
            if 'reference' in model_fields:
                result.append("    'reference': record_data.get('transaction_id', ''),")
            elif 'ref' in model_fields:
                result.append("    'ref': record_data.get('transaction_id', ''),")
            
            result.append("}")
            result.append("\nRemove fields that don't exist in the target model.")
            
            # Update result message
            full_analysis = "\n".join(result)
            self.write({'result_message': full_analysis})
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Target Model Analysis Complete',
                    'message': f'Found {len(model_fields)} fields in {self.model_name}',
                    'type': 'info',
                }
            }
            
        except KeyError:
            error_msg = f"Model '{self.model_name}' does not exist"
            self.write({'result_message': error_msg})
            raise exceptions.UserError(error_msg)
        except Exception as e:
            error_msg = f"Model analysis failed: {str(e)}"
            self.write({'result_message': error_msg})
            raise exceptions.UserError(error_msg)
        
    
    def action_precise_analysis(self):
        """Precise analysis that shows results in popup"""
        if not self.file_data:
            raise exceptions.UserError("Please upload a file first")
        
        try:
            # Decode file
            file_content = base64.b64decode(self.file_data).decode('windows-1255')
            lines = file_content.splitlines()
            
            # Find specific transaction lines
            target_lines = []
            for line in lines:
                if '9200036' in line or '9200035' in line or '9200037' in line:
                    target_lines.append(line)
                if len(target_lines) >= 3:
                    break
            
            if not target_lines:
                raise exceptions.UserError("Could not find target transaction lines")
            
            # Analyze first line in detail
            sample_line = target_lines[0]
            
            # Find key positions
            pos_id = -1
            pos_name = -1
            
            # Find transaction ID
            for tid in ['9200036', '9200035', '9200037']:
                pos = sample_line.find(tid)
                if pos >= 0:
                    pos_id = pos
                    break
            
            # Find merchant name
            for name in ['perfectomobile', 'nielsen', 'perfectom', 'niel']:
                pos = sample_line.find(name)
                if pos >= 0:
                    pos_name = pos
                    break
            
            # Find amounts
            import re
            amounts = []
            amount_matches = re.finditer(r'[+-]\d{14,15}', sample_line)
            for match in amount_matches:
                amounts.append((match.start(), match.end(), match.group()))
            
            # Create comprehensive result message
            result = []
            result.append("=== PRECISE FIELD POSITIONS ===")
            result.append(f"Sample line length: {len(sample_line)}")
            result.append("")
            
            if pos_id >= 0:
                result.append(f"Transaction ID found at position: {pos_id}")
                result.append(f"Transaction ID value: '{sample_line[pos_id:pos_id+7]}'")
            
            if pos_name >= 0:
                result.append(f"Merchant name starts at position: {pos_name}")
                result.append(f"Merchant name value: '{sample_line[pos_name:pos_name+20]}'")
            
            result.append("")
            result.append("Amount fields found:")
            for i, (start, end, amount) in enumerate(amounts):
                # Convert amount for display
                try:
                    sign = 1 if amount.startswith('+') else -1
                    amount_digits = amount[1:].lstrip('0') or '0'
                    if len(amount_digits) >= 2:
                        amount_value = float(amount_digits[:-2] + '.' + amount_digits[-2:])
                    else:
                        amount_value = float(amount_digits) / 100
                    final_amount = sign * amount_value
                    result.append(f"  Amount{i+1} at pos {start}-{end}: '{amount}' = {final_amount}")
                except:
                    result.append(f"  Amount{i+1} at pos {start}-{end}: '{amount}' = conversion failed")
            
            result.append("")
            result.append("=== CORRECTED PARSER SUGGESTION ===")
            if pos_id >= 0 and pos_name >= 0:
                result.append("Replace these lines in _parse_detail_record:")
                result.append(f"'transaction_id': line[{pos_id}:{pos_id+7}].strip(),")
                result.append(f"'customer_name': line[{pos_name}:{pos_name+30}].strip(),")
            
            if amounts:
                result.append("Amount fields:")
                for i, (start, end, _) in enumerate(amounts):
                    result.append(f"'amount{i+1}': line[{start}:{end}].strip(),")
            
            # Save to result_message AND return popup
            full_result = "\n".join(result)
            self.write({'result_message': full_result})
            
            # Return popup message
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Analysis Complete!',
                    'message': f'Found Transaction ID at pos {pos_id}, Name at pos {pos_name}. Check Result Message below for full details.',
                    'type': 'success',
                    'sticky': True,  # Keep popup visible longer
                }
            }
            
        except Exception as e:
            error_msg = f"Analysis failed: {str(e)}"
            self.write({'result_message': error_msg})
            raise exceptions.UserError(error_msg)
    def action_debug_individual_transactions(self):
        """Debug individual transactions to find correct field positions"""
        if not self.file_data:
            raise exceptions.UserError("Please upload a file first")
        
        try:
            # Decode file
            file_content = base64.b64decode(self.file_data).decode('windows-1255')
            lines = file_content.splitlines()
            
            # Find specific individual transaction lines
            target_lines = []
            for line in lines:
                if 'nielsen' in line or 'perfectomobile' in line:
                    if 'nielsen' in line:
                        target_lines.append(('nielsen', line))
                    if 'perfectomobile' in line:
                        target_lines.append(('perfectomobile', line))
                        
                if len(target_lines) >= 2:
                    break
            
            if not target_lines:
                raise exceptions.UserError("Could not find nielsen or perfectomobile lines")
            
            result = []
            result.append("=== INDIVIDUAL TRANSACTION DEBUG ===\n")
            
            for name, line in target_lines:
                result.append(f"--- {name.upper()} ANALYSIS ---")
                result.append(f"Line length: {len(line)}")
                result.append("")
                
                # Find the exact position of the name
                name_pos = line.find(name)
                result.append(f"'{name}' found at position: {name_pos}")
                
                # Show context around the name
                start_context = max(0, name_pos - 30)
                end_context = min(len(line), name_pos + len(name) + 30)
                result.append(f"Context: '{line[start_context:end_context]}'")
                result.append("")
                
                # Look for 7-digit transaction IDs (like 9200035, 9200036)
                import re
                transaction_ids = re.finditer(r'\b9\d{6}\b', line)
                result.append("Transaction ID patterns found:")
                for match in transaction_ids:
                    result.append(f"  Position {match.start()}-{match.end()}: '{match.group()}'")
                
                # Look for any 6-7 digit numbers
                general_ids = re.finditer(r'\b\d{6,7}\b', line)
                result.append("6-7 digit numbers found:")
                for match in general_ids:
                    result.append(f"  Position {match.start()}-{match.end()}: '{match.group()}'")
                
                result.append("")
                
                # Show amounts found
                amounts = re.finditer(r'[+-]\d{12,16}', line)
                result.append("Amount patterns found:")
                for match in amounts:
                    amount_str = match.group()
                    try:
                        amount_digits = amount_str[1:].lstrip('0') or '0'
                        if len(amount_digits) >= 2:
                            amount_value = float(amount_digits[:-2] + '.' + amount_digits[-2:])
                        else:
                            amount_value = float(amount_digits) / 100
                        result.append(f"  Position {match.start()}-{match.end()}: '{amount_str}' = {amount_value}")
                    except:
                        result.append(f"  Position {match.start()}-{match.end()}: '{amount_str}' = conversion failed")
                
                result.append("")
                
                # Character-by-character analysis of first 100 positions
                result.append("Character analysis (positions 0-99):")
                for pos in range(0, min(100, len(line)), 20):
                    chunk = line[pos:pos+20]
                    result.append(f"  {pos:2d}-{pos+19:2d}: '{chunk}'")
                
                result.append("")
                result.append("=" * 50)
                result.append("")
            
            # Current parser analysis
            result.append("=== CURRENT PARSER RESULTS ===")
            for name, line in target_lines:
                result.append(f"--- {name} ---")
                
                # Apply current individual transaction parser
                parsed = self._parse_individual_transaction(line)
                
                result.append(f"transaction_id: '{parsed.get('transaction_id', 'EMPTY')}'")
                result.append(f"customer_name: '{parsed.get('customer_name', 'EMPTY')}'")
                result.append(f"amount: {parsed.get('amount', 0.0)}")
                result.append("")
            
            # Suggestions
            result.append("=== SUGGESTED FIXES ===")
            result.append("Based on the analysis above:")
            result.append("1. Check where transaction IDs actually appear")
            result.append("2. Verify customer name extraction is correct")
            result.append("3. Confirm amount extraction works")
            result.append("4. Update field positions in _parse_individual_transaction")
            
            # Save result
            self.write({'result_message': '\n'.join(result)})
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Individual Transaction Debug Complete',
                    'message': 'Check Result Message for detailed analysis of nielsen/perfectomobile records',
                    'type': 'info',
                }
            }
            
        except Exception as e:
            error_msg = f"Debug failed: {str(e)}"
            self.write({'result_message': error_msg})
            raise exceptions.UserError(error_msg)