# -*- coding: utf-8 -*-
"""
Final script to create income tax menus in Odoo with JSON handling
"""

import configparser
import psycopg2
import json
import sys

# Path to your Odoo config file
ODOO_CONFIG_PATH = r"C:\workspace\odoo\odoo.conf"

def create_menus():
    # Read config
    config = configparser.ConfigParser()
    config.read(ODOO_CONFIG_PATH)
    
    # Get connection parameters
    db_params = {
        'dbname': config.get('options', 'db_name'),
        'user': config.get('options', 'db_user'),
        'password': config.get('options', 'db_password'),
        'host': config.get('options', 'db_host'),
        'port': config.get('options', 'db_port')
    }
    
    # Connect to database
    print(f"Connecting to database {db_params['dbname']} on {db_params['host']}...")
    conn = psycopg2.connect(**db_params)
    print("Connected successfully!")
    
    # Create cursor
    cur = conn.cursor()
    
    try:
        # 1. Find Israeli Reports menu (ID 295 from your output)
        israeli_reports_menu_id = 295
        print(f"Using Israeli Reports menu with ID: {israeli_reports_menu_id}")
        
        # 2. Find Configuration menu (ID 78 from your output)
        config_menu_id = 78
        print(f"Using Configuration menu with ID: {config_menu_id}")
        
        # 3. Create or find report action - in two steps to avoid JSON issues
        print("\nCreating Income Tax Report action...")
        cur.execute("SELECT id FROM ir_act_window WHERE res_model = 'l10n_il.income.tax.report.wizard'")
        result = cur.fetchone()
        if result:
            report_action_id = result[0]
            print(f"Found existing report action ID: {report_action_id}")
        else:
            # Create action in steps
            cur.execute("""
                INSERT INTO ir_act_window (res_model, view_mode, target)
                VALUES ('l10n_il.income.tax.report.wizard', 'form', 'new')
                RETURNING id
            """)
            report_action_id = cur.fetchone()[0]
            
            # Update the name separately
            cur.execute("UPDATE ir_act_window SET name = %s WHERE id = %s", 
                       ('Income Tax Report', report_action_id))
            print(f"Created report action ID: {report_action_id}")
        
        # 4. Create or find tables action - in two steps to avoid JSON issues
        print("\nCreating Income Tax Tables action...")
        cur.execute("SELECT id FROM ir_act_window WHERE res_model = 'l10n_il.income.tax'")
        result = cur.fetchone()
        if result:
            tables_action_id = result[0]
            print(f"Found existing tables action ID: {tables_action_id}")
        else:
            # Create action in steps
            cur.execute("""
                INSERT INTO ir_act_window (res_model, view_mode)
                VALUES ('l10n_il.income.tax', 'tree,form')
                RETURNING id
            """)
            tables_action_id = cur.fetchone()[0]
            
            # Update the name separately
            cur.execute("UPDATE ir_act_window SET name = %s WHERE id = %s", 
                       ('Income Tax Tables', tables_action_id))
            print(f"Created tables action ID: {tables_action_id}")
        
        # 5. Create report menu - check if exists first
        print("\nCreating Income Tax Report menu...")
        cur.execute("SELECT id FROM ir_ui_menu WHERE parent_id = %s AND action = %s", 
                   (israeli_reports_menu_id, f'ir.actions.act_window,{report_action_id}'))
        result = cur.fetchone()
        if result:
            print(f"Income Tax Report menu already exists with ID: {result[0]}")
        else:
            # Create menu with properly formatted JSON
            name_json = json.dumps({"en_US": "Income Tax Report", "he_IL": "דוחות מס הכנסה"})
            
            # First create with minimal fields
            cur.execute("""
                INSERT INTO ir_ui_menu (parent_id, sequence)
                VALUES (%s, 20)
                RETURNING id
            """, (israeli_reports_menu_id,))
            menu_id = cur.fetchone()[0]
            
            # Then update name and action separately
            cur.execute("UPDATE ir_ui_menu SET name = %s::json WHERE id = %s", 
                       (name_json, menu_id))
            cur.execute("UPDATE ir_ui_menu SET action = %s WHERE id = %s", 
                       (f'ir.actions.act_window,{report_action_id}', menu_id))
            print(f"Created Income Tax Report menu with ID: {menu_id}")
        
        # 6. Create tables menu - check if exists first
        print("\nCreating Income Tax Tables menu...")
        cur.execute("SELECT id FROM ir_ui_menu WHERE parent_id = %s AND action = %s", 
                   (config_menu_id, f'ir.actions.act_window,{tables_action_id}'))
        result = cur.fetchone()
        if result:
            print(f"Income Tax Tables menu already exists with ID: {result[0]}")
        else:
            # Create menu with properly formatted JSON
            name_json = json.dumps({"en_US": "Income Tax Tables", "he_IL": "טבלאות מס הכנסה"})
            
            # First create with minimal fields
            cur.execute("""
                INSERT INTO ir_ui_menu (parent_id, sequence)
                VALUES (%s, 20)
                RETURNING id
            """, (config_menu_id,))
            menu_id = cur.fetchone()[0]
            
            # Then update name and action separately
            cur.execute("UPDATE ir_ui_menu SET name = %s::json WHERE id = %s", 
                       (name_json, menu_id))
            cur.execute("UPDATE ir_ui_menu SET action = %s WHERE id = %s", 
                       (f'ir.actions.act_window,{tables_action_id}', menu_id))
            print(f"Created Income Tax Tables menu with ID: {menu_id}")
        
        # 7. Clear menu cache
        cur.execute("DELETE FROM ir_ui_menu_cache")
        print("\nMenu cache cleared")
        
        # Commit changes
        conn.commit()
        print("\nChanges committed successfully!")
        print("Please restart your Odoo server and refresh your browser.")
        print("\nMenu items created (in both English and Hebrew):")
        print("1. 'Income Tax Report' / 'דוחות מס הכנסה' - under Israeli Reports (ID: 295)")
        print("2. 'Income Tax Tables' / 'טבלאות מס הכנסה' - under Configuration (ID: 78)")
        
    except Exception as e:
        print(f"Error: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()
        print("Database connection closed")

if __name__ == "__main__":
    create_menus()