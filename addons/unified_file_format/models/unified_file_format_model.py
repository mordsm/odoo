from odoo import models, fields, api, exceptions
import base64
import csv
import logging
from pathlib import Path 
from datetime import datetime
import requests

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

    def _get_currency_rate(self, from_currency, to_currency='ILS'):
        """Get currency conversion rate - simplified version"""
        # In production, you should use a proper currency conversion service
        # For now, using approximate rates
        if from_currency == to_currency:
            return 1.0
        
        # Simple static rates - replace with dynamic API call in production
        rates = {
            'USD': 3.7,  # 1 USD = 3.7 ILS (approximate)
            'EUR': 4.0,  # 1 EUR = 4.0 ILS (approximate)
            'ILS': 1.0
        }
        
        try:
            # Try to get from Odoo's currency model if available
            usd_currency = self.env['res.currency'].search([('name', '=', from_currency)], limit=1)
            ils_currency = self.env['res.currency'].search([('name', '=', to_currency)], limit=1)
            
            if usd_currency and ils_currency:
                return usd_currency._convert(1.0, ils_currency, self.env.company, fields.Date.today())
        except:
            pass
        
        return rates.get(from_currency, 1.0)

    def _convert_currency(self, amount, from_currency, to_currency='ILS'):
        """Convert amount from one currency to another"""
        if from_currency == to_currency:
            return amount
        
        rate = self._get_currency_rate(from_currency, to_currency)
        return amount * rate

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
                                # FIXED: Add safety checks for logging variables
                                name = str(clean_data.get('name', 'Unknown'))[:20]
                                ref = str(clean_data.get('reference', 'No ref'))
                                amount = clean_data.get('amount', 0.0)
                                
                                # Remove non-printable characters for safe logging
                                safe_name = ''.join(c if c.isprintable() else '?' for c in name)
                                safe_ref = ''.join(c if c.isprintable() else '?' for c in ref)
                                
                                try:
                                    _logger.info(f"Created individual record: {safe_name}, Ref: {safe_ref}, Amount: {amount}")
                                except Exception as log_error:
                                    _logger.info(f"Created individual record - logging error: {str(log_error)}")
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
        """Extract dates and currency from CORRECT positions based on Hebrew specification"""
        result = {}
        
        # FIXED: Extract date from correct position (30-37) - תאריך פעולה
        if len(line) > 37:
            date_field = line[30:38].strip()  # Position 30-37 (8 characters)
            if len(date_field) == 8 and date_field.isdigit():
                # Validate it looks like a real date
                try:
                    year = int(date_field[0:4])
                    month = int(date_field[4:6])
                    day = int(date_field[6:8])
                    if 2000 <= year <= 2030 and 1 <= month <= 12 and 1 <= day <= 31:
                        result['transaction_date'] = date_field
                        result['value_date'] = date_field  # Same as transaction date
                except (ValueError, IndexError):
                    pass
        
        # FIXED: Extract currency from correct position (38-40) - סוג מטבע  
        currency = 'ILS'  # Default to ILS
        if len(line) > 40:
            currency_field = line[38:41].strip()  # Position 38-40 (3 characters)
            if currency_field in ['USD', 'EUR', 'ILS', 'שח']:
                if currency_field == 'שח':  # Hebrew for Shekel
                    currency = 'ILS'
                else:
                    currency = currency_field
            elif currency_field:  # If there's something there but not recognized
                _logger.info(f"Unknown currency code: '{currency_field}' - defaulting to ILS")
        
        result['currency'] = currency
        return result

    
    
    
    def _parse_bank_operation(self, line):
        """Parse bank operation with CORRECT field positions"""
        result = {}
        
        def clean_hebrew_text(text):
            if not text:
                return ""
            cleaned = text.replace('\x00', '').strip()
            return ''.join(char for char in cleaned if ord(char) >= 32)
        
        # Extract dates and currency from CORRECT positions
        date_currency_info = self._extract_dates_and_currency(line)
        
        # Use operation description as the main description
        description = clean_hebrew_text(line[15:30]) if len(line) > 30 else ''
        operation_details = clean_hebrew_text(line[41:52]) if len(line) > 52 else ''
        
        # Combine descriptions
        if description and operation_details:
            full_description = f"{description} {operation_details}".strip()
        elif operation_details:
            full_description = operation_details
        else:
            full_description = description or "Bank Operation"
        
        result.update({
            'transaction_id': '',  # Bank operations don't have customer transaction IDs
            'customer_name': full_description,
            'record_subtype': 'bank_operation',
            'transaction_date': date_currency_info.get('transaction_date', ''),
            'value_date': date_currency_info.get('value_date', ''),
            'currency': date_currency_info.get('currency', 'ILS')
        })
        
        # Look for amount in additional fields section (after position 70)
        amount = 0.0
        if len(line) > 70:
            remaining_line = line[70:]
            import re
            amount_matches = re.findall(r'[+-]\d{10,16}', remaining_line)
            if amount_matches:
                amount_str = amount_matches[0]
                try:
                    sign = 1 if amount_str.startswith('+') else -1
                    amount_digits = amount_str[1:].lstrip('0') or '0'
                    if len(amount_digits) >= 2:
                        amount_value = float(amount_digits[:-2] + '.' + amount_digits[-2:])
                    else:
                        amount_value = float(amount_digits) / 100
                    amount = sign * amount_value
                except ValueError:
                    amount = 0.0
        
        result['amount'] = amount
        return result

    
   
   
   
   
    def get_target_model_fields_list(self):
        """Get exact list of fields in target model for proper mapping"""
        if not self.model_name:
            raise exceptions.UserError("Please specify target model name first")
        
        try:
            target_model = self.env[self.model_name]
            model_fields = target_model._fields
            
            result = []
            result.append(f"📋 ALL FIELDS IN MODEL: {self.model_name}")
            result.append("=" * 50)
            result.append("")
            result.append("Copy this list to update your field mapping:")
            result.append("")
            
            # Sort fields alphabetically
            sorted_fields = sorted(model_fields.items())
            
            for field_name, field_obj in sorted_fields:
                field_type = field_obj.type
                is_required = getattr(field_obj, 'required', False)
                required_mark = " (REQUIRED)" if is_required else ""
                
                result.append(f"• {field_name} ({field_type}){required_mark}")
            
            result.append("")
            result.append("💡 SUGGESTED FIELD MAPPING:")
            result.append("Update _prepare_odoo_data to use these exact field names:")
            result.append("")
            
            # Suggest mapping based on common patterns
            suggestions = {}
            for field_name, field_obj in model_fields.items():
                field_type = field_obj.type
                lower_name = field_name.lower()
                
                if field_type in ['date', 'datetime'] and any(word in lower_name for word in ['date', 'time']):
                    suggestions['DATE'] = field_name
                elif field_type in ['float', 'monetary'] and any(word in lower_name for word in ['amount', 'total', 'price', 'value']):
                    suggestions['AMOUNT'] = field_name
                elif field_type == 'char' and 'name' in lower_name:
                    suggestions['NAME'] = field_name
                elif field_type == 'char' and any(word in lower_name for word in ['ref', 'reference', 'number']):
                    suggestions['REFERENCE'] = field_name
            
            for data_type, field_name in suggestions.items():
                result.append(f"'{field_name}': <-- Use for {data_type}")
            
            # Save result
            self.write({'result_message': '\n'.join(result)})
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Field List Generated',
                    'message': f'Found {len(model_fields)} fields. Check Result Message for complete list.',
                    'type': 'info',
                }
            }
            
        except Exception as e:
            error_msg = f"Field list generation failed: {str(e)}"
            self.write({'result_message': error_msg})
            raise exceptions.UserError(error_msg)
    
    
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

    def _extract_dates_and_currency(self, line):
        """Extract dates and currency from ALL correct positions based on complete specification"""
        result = {}
        
        def decode_hebrew_text(text):
            """Decode Hebrew text from windows-1255 encoding"""
            try:
                if not text or not text.strip():
                    return ""
                decoded = text.encode('latin1').decode('windows-1255')
                return decoded.strip()
            except:
                return text.strip()
        
        # תאריך ערך (Value Date) - Position 8 chars at specific location
        # Looking for pattern 20160105 (8 digits)
        import re
        date_patterns = re.findall(r'\b(20\d{6})\b', line)
        if date_patterns:
            # First date is transaction date, second (if exists) is value date
            result['transaction_date'] = date_patterns[0]
            result['value_date'] = date_patterns[1] if len(date_patterns) > 1 else date_patterns[0]
        else:
            # No dates found, use today
            from datetime import date
            today = date.today().strftime('%Y%m%d')
            result['transaction_date'] = today
            result['value_date'] = today
        
        # סוג מטבע (Currency Type) - Position showing "1USD"
        currency = 'ILS'  # Default
        currency_match = re.search(r'(\d*)(USD|EUR|ILS|שח)', line)
        if currency_match:
            currency_code = currency_match.group(2)
            if currency_code == 'שח':
                currency = 'ILS'
            else:
                currency = currency_code
        
        result['currency'] = currency
        return result

    def _parse_individual_transaction(self, line):
        """Parse individual transaction with ALL fields from specification"""
        result = {}
        
        def decode_hebrew_text(text):
            """Decode Hebrew text from windows-1255 encoding"""
            try:
                if not text or not text.strip():
                    return ""
                decoded = text.encode('latin1').decode('windows-1255')
                return decoded.strip()
            except:
                return text.strip()
        
        try:
            # Based on the Hebrew specification image, extract ALL fields:
            
            # Position 0: מחוון סוג רשומה (Record Type Indicator) - 'B'
            result['record_type'] = line[0:1] if len(line) > 0 else ''
            
            # Position 1: סוג פעולה (Operation Type) - '1'  
            result['operation_type'] = line[1:2] if len(line) > 1 else ''
            
            # Position 2-10: מספר פק/חשבון/מוביל (Account/PEK/Transporter Number)
            result['account_pek_number'] = line[2:12].strip() if len(line) > 11 else ''
            
            # Position 11: מספר מזהה ייחודי למידע בקובץ (Unique File ID) - 11 chars
            result['unique_file_id'] = line[12:23].strip() if len(line) > 22 else ''
            
            # Position 9: מספר רישיון (License Number) - 9 chars (514887249)
            result['license_number'] = line[23:32].strip() if len(line) > 31 else ''
            
            # Position 10: Additional account info
            result['account_extension'] = line[32:42].strip() if len(line) > 41 else ''
            
            # Position 5: מספר הזמנה (Order Number)
            result['order_number'] = line[42:47].strip() if len(line) > 46 else ''
            
            # Position 8: מספר פעולה או מזהה יחיד להזמנה (Transaction/Order ID)
            result['transaction_order_id'] = line[47:55].strip() if len(line) > 54 else ''
            
            # Position 15: שדה רק או שקול (Field or Equivalent) - Hebrew description
            description_field = line[55:70] if len(line) > 69 else ''
            result['description_field'] = decode_hebrew_text(description_field)
            
            # Position 43: סכום התמנעות (Main Amount) - Large number field
            amount_field = line[70:113] if len(line) > 112 else ''
            result['main_amount_field'] = amount_field.strip()
            
            # תיאור הרכישה (Purchase Description) - "הפקדת ש"ח"
            purchase_desc_start = 113
            purchase_desc_end = 130
            if len(line) > purchase_desc_end:
                purchase_desc = line[purchase_desc_start:purchase_desc_end]
                result['purchase_description'] = decode_hebrew_text(purchase_desc)
            
            # המלצה/הקטגוריה רקיע (Category/Recommendation)
            category_start = 130
            category_end = 145
            if len(line) > category_end:
                category = line[category_start:category_end]
                result['category'] = decode_hebrew_text(category)
            
            # Extract dates and currency
            date_currency_info = self._extract_dates_and_currency_complete(line)
            result.update(date_currency_info)
            
            # Position: מידע הערות עבור מק ספק/מוכר/ספק פעולה (Notes for supplier/vendor)
            notes_start = 145
            notes_end = 160
            if len(line) > notes_end:
                notes = line[notes_start:notes_end]
                result['supplier_notes'] = decode_hebrew_text(notes)
            
            # Position 4: סוג מטבע ניקוב עמלות (Currency Type with Commission) - "1USD"
            currency_commission_start = 160
            currency_commission_end = 164
            if len(line) > currency_commission_end:
                curr_comm = line[currency_commission_start:currency_commission_end]
                result['currency_commission'] = curr_comm.strip()
            
            # Position 15: סכום העמלות (Commission Amount)
            commission_amount_start = 164
            commission_amount_end = 179
            if len(line) > commission_amount_end:
                commission = line[commission_amount_start:commission_amount_end]
                result['commission_amount'] = commission.strip()
            
            # Position 15: עמלות (Additional Commission)
            additional_commission_start = 179
            additional_commission_end = 194
            if len(line) > additional_commission_end:
                add_comm = line[additional_commission_start:additional_commission_end]
                result['additional_commission'] = add_comm.strip()
            
            # Position 31: שדות שמורים או קופה טיפוסים (Reserved Fields)
            reserved_start = 194
            reserved_end = 225
            if len(line) > reserved_end:
                reserved = line[reserved_start:reserved_end]
                result['reserved_fields'] = reserved.strip()
            
            # Position 8: תיאור או קוד סוג שביל (Description/Path Type Code)
            path_code_start = 225
            path_code_end = 233
            if len(line) > path_code_end:
                path_code = line[path_code_start:path_code_end]
                result['path_type_code'] = path_code.strip()
            
            # Extract main amount from the amount fields
            main_amount = 0.0
            
            # Try to extract from main_amount_field (position 43)
            if result.get('main_amount_field'):
                amount_str = result['main_amount_field']
                # Look for amount patterns
                import re
                amount_matches = re.findall(r'[+-]?\d{10,20}', amount_str)
                if amount_matches:
                    try:
                        # Take the largest amount found
                        amounts = []
                        for match in amount_matches:
                            clean_match = match.lstrip('+-0') or '0'
                            if len(clean_match) >= 2:
                                amount_val = float(clean_match[:-2] + '.' + clean_match[-2:])
                                if match.startswith('-'):
                                    amount_val = -amount_val
                                amounts.append(amount_val)
                        
                        if amounts:
                            main_amount = max(amounts, key=abs)  # Take largest by absolute value
                    except ValueError:
                        pass
            
            # If no amount found in main field, try other amount fields
            if main_amount == 0.0:
                # Look for amount patterns in the entire line
                import re
                amount_patterns = re.findall(r'[+-]\d{10,20}', line)
                if amount_patterns:
                    try:
                        # Take first significant amount
                        for pattern in amount_patterns:
                            clean_digits = pattern[1:].lstrip('0') or '0'
                            if len(clean_digits) >= 3:  # At least 1.00
                                amount_val = float(clean_digits[:-2] + '.' + clean_digits[-2:])
                                if pattern.startswith('-'):
                                    amount_val = -amount_val
                                main_amount = amount_val
                                break
                    except ValueError:
                        pass
            
            result['amount'] = main_amount
            
            # Create customer name from available description fields
            name_parts = []
            if result.get('purchase_description'):
                name_parts.append(result['purchase_description'])
            if result.get('category'):
                name_parts.append(f"[{result['category']}]")
            if result.get('description_field'):
                name_parts.append(result['description_field'])
            
            result['customer_name'] = " ".join(name_parts) if name_parts else "Transaction"
            result['record_subtype'] = 'individual_transaction'
            
            # Use transaction_order_id as main transaction ID
            result['transaction_id'] = result.get('transaction_order_id', '')
            
            # Validation
            if not result.get('customer_name') or len(result['customer_name']) < 2:
                result['parse_error'] = f"Invalid customer name: '{result.get('customer_name', '')[:20]}'"
                return result
            
            if main_amount == 0.0:
                result['parse_error'] = f"Zero or invalid amount"
                return result
                
        except Exception as e:
            result['parse_error'] = f"Parse error: {str(e)}"
        
        return result

    def _parse_real_format(self, line):
        """Parse the ACTUAL format from your real data"""
        result = {}
        
        def decode_hebrew_text(text):
            """Decode Hebrew text from the line"""
            try:
                if not text or not text.strip():
                    return ""
                # The Hebrew text is already properly encoded in this format
                cleaned = text.replace('\x00', '').strip()
                return ''.join(char for char in cleaned if ord(char) >= 32)
            except:
                return text.strip()
        
        try:
            # REAL positions based on your actual data:
            # B10000000000251488724900000000270000100000001...
            
            # Position 0: Record Type
            result['record_type'] = line[0:1] if len(line) > 0 else ''
            
            # Position 1: Operation Type  
            result['operation_type'] = line[1:2] if len(line) > 1 else ''
            
            # Position 2-12: Account Number (10000000000)
            result['account_number'] = line[2:13].strip() if len(line) > 12 else ''
            
            # Position 13-24: File ID (251488724900) - 12 digits
            result['file_id'] = line[13:25].strip() if len(line) > 24 else ''
            
            # Position 25-33: License/Additional ID (000000027)
            result['license_number'] = line[25:34].strip() if len(line) > 33 else ''
            
            # Position 34-44: Order Number (00001000000)
            result['order_number'] = line[34:45].strip() if len(line) > 44 else ''
            
            # Position 45-52: Transaction ID (01)
            result['transaction_id'] = line[45:53].strip() if len(line) > 52 else ''
            
            # Look for Hebrew description - find "הפקדת ש'ק"
            hebrew_start = line.find('הפקדת')
            if hebrew_start >= 0:
                # Extract Hebrew description (about 20 chars)
                hebrew_desc = line[hebrew_start:hebrew_start+20]
                result['hebrew_description'] = decode_hebrew_text(hebrew_desc)
                result['customer_name'] = result['hebrew_description']
            else:
                # Fallback - look for any Hebrew characters
                import re
                hebrew_matches = re.findall(r'[\u0590-\u05FF\u200F\u200E]+(?:\s+[\u0590-\u05FF\u200F\u200E]+)*', line)
                if hebrew_matches:
                    result['hebrew_description'] = hebrew_matches[0].strip()
                    result['customer_name'] = result['hebrew_description']
                else:
                    result['customer_name'] = "Transaction"
            
            # Extract dates - look for 20160105 pattern
            import re
            date_patterns = re.findall(r'(20\d{6})', line)
            if date_patterns:
                result['transaction_date'] = date_patterns[0]  # First date
                result['value_date'] = date_patterns[1] if len(date_patterns) > 1 else date_patterns[0]
            
            # Extract currency - look for 1USD pattern
            currency_match = re.search(r'(\d+)(USD|EUR|ILS)', line)
            if currency_match:
                result['currency'] = currency_match.group(2)
            else:
                result['currency'] = 'USD'  # Default based on your data
            
            # Extract amounts - look for +followed by digits
            amount_patterns = re.findall(r'\+(\d{11,15})', line)
            amounts = []
            
            for amount_str in amount_patterns:
                try:
                    # Convert amount (last 2 digits are cents)
                    amount_digits = amount_str.lstrip('0') or '0'
                    if len(amount_digits) >= 2:
                        amount_value = float(amount_digits[:-2] + '.' + amount_digits[-2:])
                    else:
                        amount_value = float(amount_digits) / 100
                    
                    # Only consider meaningful amounts (> 0.01)
                    if amount_value > 0.01:
                        amounts.append(amount_value)
                except ValueError:
                    continue
            
            # Use the largest amount found
            if amounts:
                result['amount'] = max(amounts)
            else:
                result['amount'] = 0.0
            
            result['record_subtype'] = 'individual_transaction'
            
            # Validation
            if not result.get('customer_name') or len(result['customer_name']) < 2:
                result['parse_error'] = f"Invalid customer name: '{result.get('customer_name', '')[:20]}'"
                return result
            
            if result['amount'] == 0.0:
                result['parse_error'] = f"Zero or invalid amount"
                return result
                
        except Exception as e:
            result['parse_error'] = f"Parse error: {str(e)}"
        
        return result

    def _prepare_odoo_data(self, record_data):
        """Prepare data for financial.transaction model using EXISTING fields only"""
        if record_data.get('parse_error'):
            return None
        
        # Get fields from parsed data
        customer_name = record_data.get('customer_name', '').strip()
        transaction_id = record_data.get('transaction_id', '').strip()
        account_number = record_data.get('account_number', '').strip()
        file_id = record_data.get('file_id', '').strip()
        license_number = record_data.get('license_number', '').strip()
        record_subtype = record_data.get('record_subtype', 'unknown')
        amount = record_data.get('amount', 0.0)
        original_currency = record_data.get('currency', 'USD')
        
        # CURRENCY CONVERSION
        if original_currency != 'ILS' and amount != 0.0:
            converted_amount = self._convert_currency(amount, original_currency, 'ILS')
            _logger.info(f"Currency conversion: {amount} {original_currency} -> {converted_amount} ILS")
        else:
            converted_amount = amount
        
        # Create description
        full_description = customer_name if customer_name else f"Transaction {transaction_id}"
        
        # Build clean data using ONLY existing model fields from Image 1
        clean_data = {
            # REQUIRED FIELD
            'name': full_description[:100],  # Using 'name' field that exists
            
            # AMOUNT FIELDS (use existing fields from Image 1)
            'amount': abs(converted_amount),  # 'amount (float)' exists
        }
        
        # CREDIT/DEBIT amounts (exist in model)
        if converted_amount >= 0:
            clean_data['credit_amount'] = converted_amount  # 'credit_amount (float)' exists
            clean_data['debit_amount'] = 0.0  # 'debit_amount (float)' exists
        else:
            clean_data['credit_amount'] = 0.0
            clean_data['debit_amount'] = abs(converted_amount)
        
        # CURRENCY (exists in model)
        clean_data['currency'] = 'ILS'  # 'currency (char)' exists
        
        # TRANSACTION CODE (exists in model)  
        clean_data['transaction_code'] = record_subtype  # 'transaction_code (char)' exists
        
        # REFERENCE (exists in model)
        if transaction_id:
            clean_data['reference'] = transaction_id  # 'reference (char)' exists
        elif license_number:
            clean_data['reference'] = license_number
        
        # SEQUENCE (exists in model)
        if file_id:
            clean_data['sequence'] = file_id  # 'sequence (char)' exists
        
        # ACCOUNT NUMBER (exists in model)
        if account_number and account_number != '0' * len(account_number):
            clean_data['account_number'] = account_number  # 'account_number (char)' exists
        
        # RAW LINE (exists in model)
        if record_data.get('raw_line'):
            clean_data['raw_line'] = record_data['raw_line'][:500]  # 'raw_line (text)' exists
        
        # BALANCE (exists in model - can be same as amount)
        clean_data['balance'] = converted_amount  # 'balance (float)' exists
        
        # DATE HANDLING using existing fields
        transaction_date = record_data.get('transaction_date', '')
        if len(transaction_date) == 8 and transaction_date.isdigit():
            try:
                year = transaction_date[0:4]
                month = transaction_date[4:6]
                day = transaction_date[6:8]
                if 1 <= int(month) <= 12 and 1 <= int(day) <= 31 and int(year) >= 2000:
                    formatted_date = f"{year}-{month}-{day}"
                    clean_data['transaction_date'] = formatted_date  # 'transaction_date (date)' exists
                    
                    # VALUE DATE
                    value_date = record_data.get('value_date', '')
                    if value_date and value_date != transaction_date and len(value_date) == 8:
                        v_year = value_date[0:4]
                        v_month = value_date[4:6]
                        v_day = value_date[6:8]
                        if 1 <= int(v_month) <= 12 and 1 <= int(v_day) <= 31:
                            clean_data['value_date'] = f"{v_year}-{v_month}-{v_day}"  # 'value_date (date)' exists
                    else:
                        clean_data['value_date'] = formatted_date
                else:
                    raise ValueError("Invalid date")
            except (ValueError, IndexError):
                # Use today if date parsing fails
                from datetime import date
                today = date.today().strftime('%Y-%m-%d')
                clean_data['transaction_date'] = today
                clean_data['value_date'] = today
        else:
            # No date found, use today
            from datetime import date
            today = date.today().strftime('%Y-%m-%d')
            clean_data['transaction_date'] = today
            clean_data['value_date'] = today
        
        # Add original currency info to name if converted
        if original_currency != 'ILS':
            clean_data['name'] = f"{full_description} (was {amount} {original_currency})"[:100]
        
        # Validation
        if not clean_data.get('name') or len(clean_data['name']) < 1:
            return None
        
        if record_subtype == 'individual_transaction' and converted_amount == 0.0:
            return None
        
        return clean_data

    def test_real_data_format(self):
        """Test with your actual real data"""
        # Your actual data
        real_sample = "B10000000000251488724900000000270000100000001               0000000000000000000000000000000000000002555000הפקדת ש'ק                                         201601052016010510001                         1USD+00000000073750+00000000000000+0000000000000000000000000000001000000120160110"
        
        result = []
        result.append("🧪 REAL DATA FORMAT TEST")
        result.append("=" * 40)
        result.append(f"Sample length: {len(real_sample)} characters")
        result.append("")
        
        # Parse the real data
        parsed = self._parse_real_format(real_sample)
        
        result.append("🔍 EXTRACTED FIELDS:")
        key_fields = [
            'record_type', 'operation_type', 'account_number', 'file_id', 
            'license_number', 'order_number', 'transaction_id', 
            'customer_name', 'hebrew_description', 'transaction_date', 
            'value_date', 'currency', 'amount'
        ]
        
        for field in key_fields:
            value = parsed.get(field, 'N/A')
            result.append(f"  {field}: {value}")
        
        result.append("")
        result.append("🎯 PREPARED FOR ODOO:")
        
        # Test data preparation
        clean_data = self._prepare_odoo_data_real(parsed)
        if clean_data:
            for key, value in clean_data.items():
                result.append(f"  {key}: {value}")
            
            result.append("")
            result.append("✅ SUCCESS - Ready to create financial.transaction record!")
        else:
            result.append("❌ PREPARATION FAILED")
        
        # Check field compatibility with financial.transaction model
        result.append("")
        result.append("🔍 MODEL COMPATIBILITY CHECK:")
        
        # These are the exact fields from Image 1
        model_fields = [
            'account_number', 'amount', 'balance', 'create_date', 'create_uid',
            'credit_amount', 'currency', 'debit_amount', 'display_name', 'id',
            'name', 'raw_line', 'reference', 'sequence', 'transaction_code',
            'transaction_date', 'value_date', 'write_date', 'write_uid'
        ]
        
        if clean_data:
            compatible_count = 0
            for field_name in clean_data.keys():
                if field_name in model_fields:
                    compatible_count += 1
                    result.append(f"  ✅ {field_name}: EXISTS in model")
                else:
                    result.append(f"  ❌ {field_name}: MISSING from model")
            
            result.append("")
            result.append(f"COMPATIBILITY SCORE: {compatible_count}/{len(clean_data)} fields compatible")
        
        # Save result
        self.write({'result_message': '\n'.join(result)})
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Real Data Test Complete',
                'message': f'Parsed real format successfully! Found Hebrew: {parsed.get("hebrew_description", "N/A")[:20]}',
                'type': 'success',
            }
        }

    def _parse_detail_record(self, line):
        """Final parse method using real format"""
        result = {
            'record_type': line[0:1] if len(line) > 0 else '',
            'raw_line': line,
            'parse_error': None
        }
        
        try:
            if not line.startswith('B') or len(line) < 100:
                result['parse_error'] = f'Invalid B record'
                return result
            
            # Use real format parsing
            real_result = self._parse_real_format(line)
            result.update(real_result)
            
            # Ensure currency is set
            if not result.get('currency'):
                result['currency'] = 'USD'
            
            # Final validation
            customer_name = result.get('customer_name', '').strip()
            if not customer_name or len(customer_name) < 2:
                result['parse_error'] = "Invalid or missing description"
                return result
                
        except Exception as e:
            result['parse_error'] = f"Parse error: {str(e)}"
        
        return result
   
    
   
    # Keep all your existing analysis methods
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

  
    
    
    
   