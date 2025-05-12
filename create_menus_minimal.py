# -*- coding: utf-8 -*-
"""
Minimal script to create income tax menus in Hebrew
Uses a manual approach to avoid SQL syntax issues
"""

import configparser
import psycopg2
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
        # 1. Find VAT menu's parent (Israeli Reports menu)
        print("\nLooking for VAT report menu's parent...")
        cur.execute("SELECT parent_id FROM ir_ui_menu WHERE name LIKE '%מע%' LIMIT 1")
        result = cur.fetchone()
        if result and result[0]:
            israeli_reports_menu_id = result[0]
            print(f"Found Israeli Reports menu ID: {israeli_reports_menu_id}")
        else:
            # Try to find Israeli Reports directly
            cur.execute("SELECT id FROM ir_ui_menu WHERE name = 'Israeli Reports' LIMIT 1")
            result = cur.fetchone()
            if result:
                israeli_reports_menu_id = result[0]
                print(f"Found Israeli Reports menu ID: {israeli_reports_menu_id}")
            else:
                # Fallback to Reporting menu
                cur.execute("SELECT id FROM ir_ui_menu WHERE name = 'Reporting' LIMIT 1")
                result = cur.fetchone()
                if result:
                    israeli_reports_menu_id = result[0]
                    print(f"Using Reporting menu ID: {israeli_reports_menu_id}")
                else:
                    print("ERROR: Could not find a suitable parent menu for Income Tax Reports")
                    return
        
        # 2. Find Configuration menu
        print("\nLooking for Configuration menu...")
        cur.execute("SELECT id FROM ir_ui_menu WHERE name = 'Configuration' AND parent_id IN (SELECT id FROM ir_ui_menu WHERE name = 'Accounting') LIMIT 1")
        result = cur.fetchone()
        if result:
            config_menu_id = result[0]
            print(f"Found Configuration menu ID: {config_menu_id}")
        else:
            # Fallback to Accounting menu
            cur.execute("SELECT id FROM ir_ui_menu WHERE name = 'Accounting' LIMIT 1")
            result = cur.fetchone()
            if result:
                config_menu_id = result[0]
                print(f"Using Accounting menu ID: {config_menu_id}")
            else:
                print("ERROR: Could not find a suitable parent menu for Income Tax Tables")
                return
        
        # 3. Manual approach to create actions using separate statements for fields
        print("\nCreating Income Tax Report action...")
        # First check if report action already exists
        cur.execute("SELECT id FROM ir_act_window WHERE res_model = 'l10n_il.income.tax.report.wizard'")
        result = cur.fetchone()
        if result:
            report_action_id = result[0]
            print(f"Found existing report action ID: {report_action_id}")
        else:
            # Create a bare-bones action first
            cur.execute("INSERT INTO ir_act_window (res_model) VALUES ('l10n_il.income.tax.report.wizard') RETURNING id")
            report_action_id = cur.fetchone()[0]
            
            # Now update the fields one by one
            cur.execute("UPDATE ir_act_window SET name = 'דוחות מס הכנסה' WHERE id = %s", (report_action_id,))
            cur.execute("UPDATE ir_act_window SET view_mode = 'form' WHERE id = %s", (report_action_id,))
            cur.execute("UPDATE ir_act_window SET target = 'new' WHERE id = %s", (report_action_id,))
            print(f"Created report action ID: {report_action_id}")
        
        print("\nCreating Income Tax Tables action...")
        # Check if tables action already exists
        cur.execute("SELECT id FROM ir_act_window WHERE res_model = 'l10n_il.income.tax'")
        result = cur.fetchone()
        if result:
            tables_action_id = result[0]
            print(f"Found existing tables action ID: {tables_action_id}")
        else:
            # Create a bare-bones action first
            cur.execute("INSERT INTO ir_act_window (res_model) VALUES ('l10n_il.income.tax') RETURNING id")
            tables_action_id = cur.fetchone()[0]
            
            # Now update the fields one by one
            cur.execute("UPDATE ir_act_window SET name = 'טבלאות מס הכנסה' WHERE id = %s", (tables_action_id,))
            cur.execute("UPDATE ir_act_window SET view_mode = 'tree,form' WHERE id = %s", (tables_action_id,))
            print(f"Created tables action ID: {tables_action_id}")
        
        # 4. Check if Income Tax Report menu already exists
        print("\nCreating Income Tax Report menu...")
        cur.execute("SELECT id FROM ir_ui_menu WHERE name = 'דוחות מס הכנסה' AND parent_id = %s", (israeli_reports_menu_id,))
        result = cur.fetchone()
        if result:
            print(f"Income Tax Report menu already exists: {result[0]}")
        else:
            # Create a bare-bones menu first
            cur.execute("INSERT INTO ir_ui_menu (parent_id, sequence) VALUES (%s, 20) RETURNING id", (israeli_reports_menu_id,))
            menu_id = cur.fetchone()[0]
            
            # Update fields one by one
            cur.execute("UPDATE ir_ui_menu SET name = 'דוחות מס הכנסה' WHERE id = %s", (menu_id,))
            cur.execute("UPDATE ir_ui_menu SET action = %s WHERE id = %s", 
                       (f'ir.actions.act_window,{report_action_id}', menu_id))
            print(f"Created Income Tax Report menu ID: {menu_id}")
        
        # 5. Check if Income Tax Tables menu already exists
        print("\nCreating Income Tax Tables menu...")
        cur.execute("SELECT id FROM ir_ui_menu WHERE name = 'טבלאות מס הכנסה' AND parent_id = %s", (config_menu_id,))
        result = cur.fetchone()
        if result:
            print(f"Income Tax Tables menu already exists: {result[0]}")
        else:
            # Create a bare-bones menu first
            cur.execute("INSERT INTO ir_ui_menu (parent_id, sequence) VALUES (%s, 20) RETURNING id", (config_menu_id,))
            menu_id = cur.fetchone()[0]
            
            # Update fields one by one
            cur.execute("UPDATE ir_ui_menu SET name = 'טבלאות מס הכנסה' WHERE id = %s", (menu_id,))
            cur.execute("UPDATE ir_ui_menu SET action = %s WHERE id = %s", 
                       (f'ir.actions.act_window,{tables_action_id}', menu_id))
            print(f"Created Income Tax Tables menu ID: {menu_id}")
        
        # 6. Clear menu cache
        cur.execute("DELETE FROM ir_ui_menu_cache")
        print("\nMenu cache cleared")
        
        # Commit changes
        conn.commit()
        print("\nChanges committed successfully!")
        print("Please restart your Odoo server and refresh your browser.")
        
    except Exception as e:
        print(f"Error: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()
        print("Database connection closed")

if __name__ == "__main__":
    create_menus()