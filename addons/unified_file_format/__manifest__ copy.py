# __manifest__.py
{
    'name': 'Israel Tax Authority Unified File Import',
    'version': '18.0.1.0.0',
    'category': 'Accounting/Localizations',
    'summary': 'Import unified file from Israel Tax Authority to create new company',
    'description': '''
        Israel Tax Authority Unified File Import
        ========================================
        
        This module allows importing the unified file format from Israel Tax Authority
        to automatically create a new company in Odoo with all accounting data.
        
        Key Features:
        -------------
        * Import company details (name, VAT, address, contact info)
        * Create complete chart of accounts with proper account types
        * Import customers and suppliers with full contact details
        * Import products/items with pricing information
        * Import opening balances for all accounts
        * Import historical journal entries and transactions
        * Support for multiple file formats and encodings
        * Hebrew language support with proper UTF-8/Windows-1255 encoding
        * Israeli VAT number validation and formatting
        * Comprehensive error handling and detailed logging
        * Progress tracking for large imports
        * Wizard for quick imports and advanced import options
        
        Supported File Formats:
        ----------------------
        * Pipe-delimited format (FIELD|VALUE)
        * CSV format with various delimiters (comma, semicolon, tab)
        * XML structured format
        * Fixed-width format
        * Multiple character encodings automatically detected
        
        Import Process:
        ---------------
        1. Upload unified file through user-friendly interface
        2. Automatic file analysis and data extraction
        3. Preview extracted information before import
        4. Flexible import options (choose what to import)
        5. Create new company or import to existing company
        6. Automatic data validation and error reporting
        7. Detailed success/error logs for troubleshooting
        
        Technical Features:
        ------------------
        * Handles large files efficiently (up to 50MB)
        * Memory-optimized parsing for better performance
        * Automatic encoding detection (UTF-8, Windows-1255, ISO-8859-8)
        * Duplicate detection and prevention
        * Transaction rollback on errors
        * Comprehensive audit trail
        * Multi-company support
        
        Business Benefits:
        -----------------
        * Dramatically reduces manual data entry time
        * Eliminates human errors in data migration
        * Ensures compliance with Israeli accounting standards
        * Maintains data integrity during company transitions
        * Supports accountants and bookkeepers workflow
        * Facilitates software migrations between accounting systems
    ''',
    'author': 'Your Company Name',
    'website': 'https://www.yourcompany.com',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'account',
        'contacts', 
        'product',
        'l10n_il',  # Israeli localization
        'mail',     # For messaging and activity tracking
    ],
    'data': [
        # Security
        'security/ir.model.access.csv',
        'security/unified_import_security.xml',
        
        # Data
        'data/ir_sequence_data.xml',
        'data/account_journal_data.xml',
        
        # Views
        'views/unified_file_import_views.xml',
        'views/unified_file_import_menu.xml',
        
        # Wizards
        'wizards/unified_file_import_wizard_views.xml',
        
        # Reports (optional)
        'reports/import_summary_report.xml',
    ],
    'demo': [
        # Demo data for testing
        'demo/unified_file_demo.xml',
        'demo/sample_files.xml',
    ],
    'qweb': [
        # Static web assets if needed
        'static/src/xml/import_progress.xml',
    ],
    'external_dependencies': {
        'python': [
            'chardet',      # For automatic encoding detection
            'xlrd',         # For Excel file support (future enhancement)
            'openpyxl',     # For modern Excel files (future enhancement)
        ],
    },
    'images': [
        'static/description/banner.png',
        'static/description/icon.png',
        'static/description/screenshot1.png',
        'static/description/screenshot2.png',
    ],
    'assets': {
        'web.assets_backend': [
            'unified_file_import/static/src/css/import_progress.css',
            'unified_file_import/static/src/js/import_progress.js',
        ],
    },
    'installable': True,
    'auto_install': False,
    'application': True,  # This is a standalone application
    'sequence': 150,      # Menu sequence
    'price': 0.00,       # If you plan to sell this module
    'currency': 'EUR',   # Currency for price
    
    # Post-install configuration
    'post_init_hook': '_post_install_hook',
    'uninstall_hook': '_uninstall_hook',
    
    # Version compatibility
    'odoo_version': '16.0',
    
    # Development info
    'maintainer': 'Your Name <your.email@company.com>',
    'contributors': [
        'Developer 1 <dev1@company.com>',
        'Developer 2 <dev2@company.com>',
    ],
    
    # Support and documentation
    'support': 'support@yourcompany.com',
    'documentation': 'https://docs.yourcompany.com/unified-file-import',
    
    # Module state and quality
    'installable': True,
    'auto_install': False,
    'application': True,
}