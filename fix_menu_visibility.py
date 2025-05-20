# -*- coding: utf-8 -*-
"""
Script to fix menu visibility issues with proper JSON handling
"""

import configparser
import psycopg2
import json
import sys

# Path to your Odoo config file
ODOO_CONFIG_PATH = r"C:\workspace\odoo\odoo.conf"

def fix_menu_visibility():
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
        # 1. Simple check for VAT menu without string_agg
        print("\nChecking VAT report menu...")
        cur.execute("""
            SELECT m.id, m.name, m.parent_id
            FROM ir_ui_menu m
            WHERE (m.name::text ILIKE '%VAT%' OR m.name::text ILIKE '%מע%')
            AND m.parent_id = 295
            LIMIT 1
        """)
        vat_menu = cur.fetchone()
        
        if vat_menu:
            vat_menu_id = vat_menu[0]
            vat_menu_name = vat_menu[1]
            vat_menu_parent_id = vat_menu[2]
            
            print(f"VAT menu ID: {vat_menu_id}")
            print(f"VAT menu name: {vat_menu_name}")
            print(f"VAT menu parent ID: {vat_menu_parent_id}")
            
            # Check groups for VAT menu
            print("\nChecking groups for VAT menu...")
            cur.execute("""
                SELECT g.id, g.name
                FROM ir_ui_menu_group_rel mg
                JOIN res_groups g ON mg.gid = g.id
                WHERE mg.menu_id = %s
            """, (vat_menu_id,))
            
            vat_groups = cur.fetchall()
            if vat_groups:
                print(f"VAT menu has {len(vat_groups)} groups:")
                for group in vat_groups:
                    print(f"  - Group ID: {group[0]}, Name: {group[1]}")
            else:
                print("VAT menu has no groups assigned")
            
            # 2. Check Income Tax menus
            print("\nChecking Income Tax menus...")
            cur.execute("""
                SELECT m.id, m.name, m.parent_id, m.action
                FROM ir_ui_menu m
                WHERE m.name::text ILIKE '%Income Tax%'
            """)
            
            income_tax_menus = cur.fetchall()
            
            if income_tax_menus:
                print(f"Found {len(income_tax_menus)} Income Tax menus:")
                
                for menu in income_tax_menus:
                    menu_id = menu[0]
                    menu_name = menu[1]
                    parent_id = menu[2]
                    action = menu[3]
                    
                    print(f"\nMenu ID: {menu_id}")
                    print(f"Menu name: {menu_name}")
                    print(f"Parent ID: {parent_id}")
                    print(f"Action: {action}")
                    
                    # Check if menu has groups
                    cur.execute("""
                        SELECT COUNT(*)
                        FROM ir_ui_menu_group_rel
                        WHERE menu_id = %s
                    """, (menu_id,))
                    
                    group_count = cur.fetchone()[0]
                    print(f"Menu has {group_count} groups assigned")
                    
                    # 3. Copy the group settings from VAT menu if it has groups
                    if vat_groups:
                        print(f"Applying VAT menu group settings to menu {menu_id}...")
                        
                        # First delete existing group relations
                        cur.execute("DELETE FROM ir_ui_menu_group_rel WHERE menu_id = %s", (menu_id,))
                        print(f"Removed existing group assignments for menu {menu_id}")
                        
                        # Add the VAT menu groups
                        for group in vat_groups:
                            cur.execute("""
                                INSERT INTO ir_ui_menu_group_rel (menu_id, gid)
                                VALUES (%s, %s)
                            """, (menu_id, group[0]))
                        
                        print(f"Added {len(vat_groups)} groups to menu {menu_id}")
                    elif group_count > 0:
                        # If VAT menu has no groups but this menu does, remove them to make it visible to all
                        cur.execute("DELETE FROM ir_ui_menu_group_rel WHERE menu_id = %s", (menu_id,))
                        print(f"Removed {group_count} existing group assignments to make menu visible to all users")
            else:
                print("No Income Tax menus found!")
                
            # 4. Check and update active status
            print("\nUpdating active status...")
            cur.execute("UPDATE ir_ui_menu SET active = TRUE WHERE name::text ILIKE '%Income Tax%'")
            updated = cur.rowcount
            print(f"Updated active status for {updated} menus")
            
            # 5. Check action configuration
            print("\nChecking action configuration...")
            cur.execute("""
                SELECT id, name, binding_view_types
                FROM ir_act_window
                WHERE (name::text ILIKE '%Income Tax%' OR res_model ILIKE '%income.tax%')
            """)
            
            actions = cur.fetchall()
            for action in actions:
                action_id = action[0]
                action_name = action[1]
                binding_view_types = action[2]
                
                print(f"Action ID: {action_id}")
                print(f"Action name: {action_name}")
                print(f"Binding view types: {binding_view_types or 'None'}")
                
                # Update binding view types if needed
                if not binding_view_types:
                    cur.execute("""
                        UPDATE ir_act_window
                        SET binding_view_types = 'list,form'
                        WHERE id = %s
                    """, (action_id,))
                    print(f"Updated binding view types for action {action_id}")
            
            # 6. Verify parent menus are visible
            print("\nVerifying parent menus...")
            cur.execute("SELECT id, name, active FROM ir_ui_menu WHERE id IN (295, 78)")
            parent_menus = cur.fetchall()
            
            for menu in parent_menus:
                menu_id = menu[0]
                menu_name = menu[1]
                active = menu[2]
                
                print(f"Parent menu ID: {menu_id}")
                print(f"Parent menu name: {menu_name}")
                print(f"Active: {active}")
                
                if not active:
                    cur.execute("UPDATE ir_ui_menu SET active = TRUE WHERE id = %s", (menu_id,))
                    print(f"Activated parent menu {menu_id}")
                    
            # 7. Try to add menus to all users with access to VAT menu
            print("\nChecking user access...")
            cur.execute("""
                SELECT DISTINCT u.id, u.login
                FROM res_users u
                JOIN res_groups_users_rel gu ON u.id = gu.uid
                JOIN ir_ui_menu_group_rel mg ON gu.gid = mg.gid
                WHERE mg.menu_id = %s
                AND u.active = TRUE
            """, (vat_menu_id,))
            
            users = cur.fetchall()
            print(f"Found {len(users)} users with access to VAT menu")
            
            # Just for informational purposes - we handle access through groups
            for user in users:
                print(f"User ID: {user[0]}, Login: {user[1]}")
        else:
            print("VAT menu not found! Checking for any VAT menu...")
            
            # Try a broader search
            cur.execute("""
                SELECT m.id, m.name, m.parent_id
                FROM ir_ui_menu m
                WHERE m.name::text ILIKE '%VAT%' OR m.name::text ILIKE '%מע%'
                LIMIT 5
            """)
            
            vat_menus = cur.fetchall()
            if vat_menus:
                print(f"Found {len(vat_menus)} potential VAT menus:")
                for menu in vat_menus:
                    print(f"  - ID: {menu[0]}, Name: {menu[1]}, Parent ID: {menu[2]}")
            else:
                print("No VAT menus found at all!")
            
            # Still check Income Tax menus
            print("\nChecking Income Tax menus anyway...")
            cur.execute("""
                SELECT m.id, m.name, m.parent_id, m.action
                FROM ir_ui_menu m
                WHERE m.name::text ILIKE '%Income Tax%'
            """)
            
            income_tax_menus = cur.fetchall()
            if income_tax_menus:
                print(f"Found {len(income_tax_menus)} Income Tax menus:")
                for menu in income_tax_menus:
                    print(f"  - ID: {menu[0]}, Name: {menu[1]}, Parent ID: {menu[2]}, Action: {menu[3]}")
                
                # Update active status
                cur.execute("UPDATE ir_ui_menu SET active = TRUE WHERE name::text ILIKE '%Income Tax%'")
                updated = cur.rowcount
                print(f"Updated active status for {updated} menus")
                
                # Remove any group restrictions to make menus visible to everyone
                for menu in income_tax_menus:
                    cur.execute("DELETE FROM ir_ui_menu_group_rel WHERE menu_id = %s", (menu[0],))
                    print(f"Removed group restrictions for menu {menu[0]}")
            else:
                print("No Income Tax menus found!")
        
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
    fix_menu_visibility()