# -*- coding: utf-8 -*-
"""
This script creates the necessary menu items for Israeli Income Tax.
It reads the connection parameters directly from the Odoo config file.

Save this file next to your odoo.conf file and run it:
python create_menus_fixed.py
"""

import configparser
import os
import psycopg2
import sys

# Path to your Odoo config file - update this to match your system
ODOO_CONFIG_PATH = r"C:\workspace\odoo\odoo.conf"

def read_odoo_config(config_path):
    """Read the Odoo configuration file and extract database settings."""
    config = configparser.ConfigParser()
    config.read(config_path)
    
    # Get database connection parameters
    db_params = {
        'dbname': config.get('options', 'db_name'),
        'user': config.get('options', 'db_user'),
        'password': config.get('options', 'db_password'),
        'host': config.get('options', 'db_host'),
        'port': config.get('options', 'db_port')
    }
    
    return db_params

def create_menu_items(db_params):
    """Create menu items directly in the database."""
    conn = None
    try:
        # Connect to the PostgreSQL database
        print(f"Connecting to database {db_params['dbname']} on {db_params['host']}...")
        conn = psycopg2.connect(
            dbname=db_params['dbname'],
            user=db_params['user'],
            password=db_params['password'],
            host=db_params['host'],
            port=db_params['port']
        )
        
        print("Connected successfully!")
        
        # Create a cursor
        cur = conn.cursor()
        
        # Step 1: Find the action IDs if they exist
        cur.execute("SELECT id FROM ir_act_window WHERE res_model = 'l10n_il.income.tax.report.wizard'")
        result = cur.fetchone()
        if result:
            report_action_id = result[0]
            print(f"Found existing report action ID: {report_action_id}")
        else:
            # Create the report action with parameters to avoid Hebrew issues
            cur.execute("""
                INSERT INTO ir_act_window (name, res_model, view_mode, target)
                VALUES (%s, %s, %s, %s)
                RETURNING id
            """, ('Income Tax Reports', 'l10n_il.income.tax.report.wizard', 'form', 'new'))
            report_action_id = cur.fetchone()[0]
            print(f"Created new report action ID: {report_action_id}")
        
        # Step 2: Find or create the income tax tables action
        cur.execute("SELECT id FROM ir_act_window WHERE res_model = 'l10n_il.income.tax'")
        result = cur.fetchone()
        if result:
            tables_action_id = result[0]
            print(f"Found existing tables action ID: {tables_action_id}")
        else:
            # Create the tables action with parameters
            cur.execute("""
                INSERT INTO ir_act_window (name, res_model, view_mode)
                VALUES (%s, %s, %s)
                RETURNING id
            """, ('Income Tax Tables', 'l10n_il.income.tax', 'tree,form'))
            tables_action_id = cur.fetchone()[0]
            print(f"Created new tables action ID: {tables_action_id}")
        
        # Step 3: Find menus with VAT reports - using a more careful query
        print("\nSearching for VAT report menus...")
        cur.execute("SELECT id, name, parent_id FROM ir_ui_menu WHERE name LIKE '%VAT%' OR name LIKE '%מע%'")
        vat_menus = cur.fetchall()
        
        if vat_menus:
            print(f"Found {len(vat_menus)} potential VAT report menus:")
            israeli_reports_menu_id = None
            
            for menu_id, menu_name, parent_id in vat_menus:
                print(f"  - ID: {menu_id}, Name: {menu_name}, Parent ID: {parent_id}")
                
                # Get parent menu name
                if parent_id:
                    cur.execute("SELECT name FROM ir_ui_menu WHERE id = %s", (parent_id,))
                    parent_result = cur.fetchone()
                    if parent_result:
                        parent_name = parent_result[0]
                        print(f"    Parent menu: {parent_name} (ID: {parent_id})")
                        
                        # This is likely the Israeli Reports menu
                        israeli_reports_menu_id = parent_id
            
            if not israeli_reports_menu_id and vat_menus and vat_menus[0][2]:
                print("Could not determine the Israeli Reports menu. Using the parent of the first VAT menu.")
                israeli_reports_menu_id = vat_menus[0][2]
        else:
            print("No VAT report menus found. Looking for Israeli Reports menu directly...")
            # Try to find the Israeli Reports menu
            cur.execute("SELECT id FROM ir_ui_menu WHERE name = 'Israeli Reports'")
            result = cur.fetchone()
            if result:
                israeli_reports_menu_id = result[0]
                print(f"Found Israeli Reports menu ID: {israeli_reports_menu_id}")
            else:
                print("No Israeli Reports menu found. Looking for main reports menu...")
                # Try to find the main reports menu
                cur.execute("SELECT id FROM ir_ui_menu WHERE name IN ('Reporting', 'Reports')")
                result = cur.fetchone()
                if result:
                    israeli_reports_menu_id = result[0]
                    print(f"Using main reports menu: {israeli_reports_menu_id}")
                else:
                    print("ERROR: Cannot find reports menu")
                    return
        
        # Step 4: Find the configuration menu
        print("\nSearching for configuration menu...")
        cur.execute("""
            SELECT id FROM ir_ui_menu 
            WHERE name IN ('Configuration', 'Settings')
            AND parent_id IN (SELECT id FROM ir_ui_menu WHERE name IN ('Accounting', 'Finance'))
        """)
        result = cur.fetchone()
        if result:
            config_menu_id = result[0]
            print(f"Found configuration menu ID: {config_menu_id}")
        else:
            print("No configuration menu found. Looking for main accounting menu...")
            cur.execute("SELECT id FROM ir_ui_menu WHERE name IN ('Accounting', 'Finance')")
            result = cur.fetchone()
            if result:
                config_menu_id = result[0]
                print(f"Using main accounting menu: {config_menu_id}")
            else:
                print("ERROR: Cannot find configuration menu")
                return
        
        # Step 5: Check if the income tax report menu already exists
        cur.execute("""
            SELECT id FROM ir_ui_menu 
            WHERE name = 'Income Tax Reports' AND parent_id = %s
        """, (israeli_reports_menu_id,))
        result = cur.fetchone()
        if result:
            print(f"Income tax report menu already exists: {result[0]}")
        else:
            # Create the income tax report menu - using parameters and English name
            cur.execute("""
                INSERT INTO ir_ui_menu (name, parent_id, action, sequence)
                VALUES (%s, %s, %s, %s)
                RETURNING id
            """, ('Income Tax Reports', israeli_reports_menu_id, 'ir.actions.act_window,' + str(report_action_id), 20))
            menu_id = cur.fetchone()[0]
            print(f"Created income tax report menu ID: {menu_id}")
        
        # Step 6: Check if the income tax tables menu already exists
        cur.execute("""
            SELECT id FROM ir_ui_menu 
            WHERE name = 'Income Tax Tables' AND parent_id = %s
        """, (config_menu_id,))
        result = cur.fetchone()
        if result:
            print(f"Income tax tables menu already exists: {result[0]}")
        else:
            # Create the income tax tables menu - using parameters and English name
            cur.execute("""
                INSERT INTO ir_ui_menu (name, parent_id, action, sequence)
                VALUES (%s, %s, %s, %s)
                RETURNING id
            """, ('Income Tax Tables', config_menu_id, 'ir.actions.act_window,' + str(tables_action_id), 20))
            menu_id = cur.fetchone()[0]
            print(f"Created income tax tables menu ID: {menu_id}")
        
        # Step 7: Clear the menu cache
        cur.execute("DELETE FROM ir_ui_menu_cache")
        print("Menu cache cleared")
        
        # Commit the changes
        conn.commit()
        print("\nChanges committed successfully!")
        print("Please restart your Odoo server and refresh your browser.")
        print("\nNote: The menu items were created with English names to avoid character encoding issues.")
        print("Menu items created:")
        print("1. 'Income Tax Reports' - next to your VAT reports")
        print("2. 'Income Tax Tables' - in the Configuration menu")
        
    except (Exception, psycopg2.DatabaseError) as error:
        print(f"Error: {error}")
        if conn:
            conn.rollback()
    finally:
        # Close the connection
        if conn:
            conn.close()
            print("Database connection closed")

if __name__ == "__main__":
    if not os.path.exists(ODOO_CONFIG_PATH):
        print(f"Error: Config file not found at {ODOO_CONFIG_PATH}")
        print("Please update the ODOO_CONFIG_PATH variable in the script to point to your odoo.conf file")
        sys.exit(1)
        
    db_params = read_odoo_config(ODOO_CONFIG_PATH)
    create_menu_items(db_params)