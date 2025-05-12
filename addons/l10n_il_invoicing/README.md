# Israel - VAT Reporting for Odoo Community

This module adds Israel-specific VAT reporting functionality to Odoo Community Edition without requiring the full Accounting module.

## Features

- VAT report accessible from the Invoicing app (no need for Accounting module)
- Standard Israeli VAT tax codes (18%, exempt, export, import)
- VAT report generation compatible with Israeli Tax Authority requirements (PCN 874 format)
- Detailed transaction view for auditing

## Installation

1. Copy the `l10n_il_invoicing` folder to your Odoo addons directory
2. Update the addons list in Odoo
3. Install the module via the Odoo Apps interface

## Configuration

After installation:

1. Go to Invoicing → Configuration → Taxes
2. Verify that the Israeli tax codes are correctly set up
3. Assign the appropriate tax codes to your products/services

## Usage

To create and submit a VAT report:

1. Go to Invoicing → Reports → Israeli Reports → VAT Reports
2. Create a new report by specifying the reporting period
3. Click "Calculate" to generate the report
4. Review the calculated values
5. Click "Generate Report File" to create the file for submission
6. Download the generated file and submit it to the Israeli Tax Authority

## Technical Information

This module extends the Invoicing app to support Israeli VAT reporting without requiring the Accounting module. It creates:

- Custom models for VAT reporting
- Extensions to the existing tax models
- Israeli-specific tax codes
- Report generation in the required format

## Compatibility

- Odoo Community Edition v14.0 and above
- Tested with Odoo v16.0

## Support

For support requests, please contact your Odoo service provider or create an issue in the repository.

## License

LGPL-3.0