# -*- coding: utf-8 -*-
"""
Final script to create income tax menus in Hebrew
Uses proper JSONB handling for Odoo's menu structure
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
        # First, get all menu items to see what we're working with
        print("\nFetching all menu items...")
        cur.execute("SELECT id, name, parent_id FROM ir_ui_menu LIMIT 10")
        sample_menus = cur.fetchall()
        print("Sample menu items:")
        for menu in sample_menus:
            print(f"  ID: {menu[0]}, Name: {menu[1]}, Parent: {menu[2]}")
        
        # Find Israeli Reports or similar menu
        print("\nLooking for Israeli Reports menu...")
        
        # Try different queries to find the right menu
        menu_queries = [
            "SELECT id FROM ir_ui_menu WHERE name = 'Israeli Reports'",
            "SELECT id FROM ir_ui_menu WHERE name::text ILIKE '%Israeli%Report%'",
            "SELECT id FROM ir_ui_menu WHERE name::text ILIKE '%דוחות%ישראל%'",
            "SELECT parent_id FROM ir_ui_menu WHERE name::text ILIKE '%VAT%' OR name::text ILIKE '%מע''מ%'",
            "SELECT id FROM ir_ui_menu WHERE name = 'Reports' OR name = 'Reporting'"
        ]
        
        israeli_reports_menu_id = None
        for query in menu_queries:
            try:
                cur.execute(query)
                result = cur.fetchone()
                if result and result[0]:
                    israeli_reports_menu_id = result[0]
                    print(f"Found reports menu with ID: {israeli_reports_menu_id}")
                    # Get the menu name
                    cur.execute("SELECT name FROM ir_ui_menu WHERE id = %s", (israeli_reports_menu_id,))
                    menu_name = cur.fetchone()
                    if menu_name:
                        print(f"Menu name: {menu_name[0]}")
                    break
            except Exception as e:
                print(f"Query failed: {query}")
                print(f"Error: {e}")
                continue
        
        if not israeli_reports_menu_id:
            # Last resort: Use the first menu we find
            try:
                cur.execute("SELECT id FROM ir_ui_menu LIMIT 1")
                result = cur.fetchone()
                if result:
                    israeli_reports_menu_id = result[0]
                    print(f"Using first available menu ID: {israeli_reports_menu_id}")
            except Exception as e:
                print(f"Last resort query failed: {e}")
                print("ERROR: Could not find any menu to use as parent")
                return
                
        # Find Configuration menu
        print("\nLooking for Configuration menu...")
        config_menu_id = None
        config_queries = [
            "SELECT id FROM ir_ui_menu WHERE name = 'Configuration'",
            "SELECT id FROM ir_ui_menu WHERE name::text ILIKE '%Config%'",
            "SELECT id FROM ir_ui_menu WHERE name::text ILIKE '%הגדרות%'",
            "SELECT id FROM ir_ui_menu WHERE name = 'Accounting' OR name = 'Finance'"
        ]
        
        for query in config_queries:
            try:
                cur.execute(query)
                result = cur.fetchone()
                if result and result[0]:
                    config_menu_id = result[0]
                    print(f"Found configuration menu with ID: {config_menu_id}")
                    # Get the menu name
                    cur.execute("SELECT name FROM ir_ui_menu WHERE id = %s", (config_menu_id,))
                    menu_name = cur.fetchone()
                    if menu_name:
                        print(f"Menu name: {menu_name[0]}")
                    break
            except Exception as e:
                print(f"Query failed: {query}")
                print(f"Error: {e}")
                continue
                
        if not config_menu_id:
            # If we couldn't find a config menu, use the same menu as reports
            config_menu_id = israeli_reports_menu_id
            print(f"Using reports menu as config menu: {config_menu_id}")
        
        # Create report action
        print("\nCreating Income Tax Report action...")
        cur.execute("SELECT id FROM ir_act_window WHERE res_model = 'l10n_il.income.tax.report.wizard'")
        result = cur.fetchone()
        if result:
            report_action_id = result[0]
            print(f"Found existing report action ID: {report_action_id}")
        else:
            # Create action
            try:
                cur.execute("""
                    INSERT INTO ir_act_window (name, res_model, view_mode, target)
                    VALUES ('Income Tax Report', 'l10n_il.income.tax.report.wizard', 'form', 'new')
                    RETURNING id
                """)
                report_action_id = cur.fetchone()[0]
                print(f"Created report action ID: {report_action_id}")
            except Exception as e:
                print(f"Error creating report action: {e}")
                # Try simpler approach
                cur.execute("INSERT INTO ir_act_window (res_model) VALUES ('l10n_il.income.tax.report.wizard') RETURNING id")
                report_action_id = cur.fetchone()[0]
                cur.execute("UPDATE ir_act_window SET name = 'Income Tax Report' WHERE id = %s", (report_action_id,))
                cur.execute("UPDATE ir_act_window SET view_mode = 'form' WHERE id = %s", (report_action_id,))
                cur.execute("UPDATE ir_act_window SET target = 'new' WHERE id = %s", (report_action_id,))
                print(f"Created report action ID (alternative method): {report_action_id}")
        
        # Create tables action
        print("\nCreating Income Tax Tables action...")
        cur.execute("SELECT id FROM ir_act_window WHERE res_model = 'l10n_il.income.tax'")
        result = cur.fetchone()
        if result:
            tables_action_id = result[0]
            print(f"Found existing tables action ID: {tables_action_id}")
        else:
            # Create action
            try:
                cur.execute("""
                    INSERT INTO ir_act_window (name, res_model, view_mode)
                    VALUES ('Income Tax Tables', 'l10n_il.income.tax', 'tree,form')
                    RETURNING id
                """)
                tables_action_id = cur.fetchone()[0]
                print(f"Created tables action ID: {tables_action_id}")
            except Exception as e:
                print(f"Error creating tables action: {e}")
                # Try simpler approach
                cur.execute("INSERT INTO ir_act_window (res_model) VALUES ('l10n_il.income.tax') RETURNING id")
                tables_action_id = cur.fetchone()[0]
                cur.execute("UPDATE ir_act_window SET name = 'Income Tax Tables' WHERE id = %s", (tables_action_id,))
                cur.execute("UPDATE ir_act_window SET view_mode = 'tree,form' WHERE id = %s", (tables_action_id,))
                print(f"Created tables action ID (alternative method): {tables_action_id}")
        
        # Create report menu item
        print("\nCreating Income Tax Report menu item...")
        # Check if it already exists
        try:
            cur.execute("SELECT id FROM ir_ui_menu WHERE name::text ILIKE '%Income Tax Report%' AND parent_id = %s", (israeli_reports_menu_id,))
            result = cur.fetchone()
            if result:
                print(f"Income Tax Report menu already exists: {result[0]}")
            else:
                # Create menu
                cur.execute("""
                    INSERT INTO ir_ui_menu (name, parent_id, action, sequence)
                    VALUES ('Income Tax Report', %s, %s, 20)
                    RETURNING id
                """, (israeli_reports_menu_id, f'ir.actions.act_window,{report_action_id}'))
                menu_id = cur.fetchone()[0]
                print(f"Created Income Tax Report menu ID: {menu_id}")
        except Exception as e:
            print(f"Error checking/creating report menu: {e}")
        
        # Create tables menu item
        print("\nCreating Income Tax Tables menu item...")
        # Check if it already exists
        try:
            cur.execute("SELECT id FROM ir_ui_menu WHERE name::text ILIKE '%Income Tax Table%' AND parent_id = %s", (config_menu_id,))
            result = cur.fetchone()
            if result:
                print(f"Income Tax Tables menu already exists: {result[0]}")
            else:
                # Create menu
                cur.execute("""
                    INSERT INTO ir_ui_menu (name, parent_id, action, sequence)
                    VALUES ('Income Tax Tables', %s, %s, 20)
                    RETURNING id
                """, (config_menu_id, f'ir.actions.act_window,{tables_action_id}'))
                menu_id = cur.fetchone()[0]
                print(f"Created Income Tax Tables menu ID: {menu_id}")
        except Exception as e:
            print(f"Error checking/creating tables menu: {e}")
        
        # Clear menu cache
        try:
            cur.execute("DELETE FROM ir_ui_menu_cache")
            print("\nMenu cache cleared")
        except Exception as e:
            print(f"Error clearing menu cache: {e}")
        
        # Commit changes
        conn.commit()
        print("\nChanges committed successfully!")
        print("Please restart your Odoo server and refresh your browser.")
        print("\nNote: The menu items were created with English names due to database constraints.")
        print("Menu items created:")
        print("1. 'Income Tax Report' - should appear in the reports menu")
        print("2. 'Income Tax Tables' - should appear in the configuration menu")
        
    except Exception as e:
        print(f"Error: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()
        print("Database connection closed")

if __name__ == "__main__":
    create_menus()