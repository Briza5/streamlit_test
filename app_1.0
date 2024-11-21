import streamlit as st
import pandas as pd
from snowflake.connector import connect
import datetime
import os

# Debug informace
print("=== DEBUG INFO START ===")
print("Current working directory:", os.getcwd())
print("Streamlit secrets type:", type(st.secrets))
print("Streamlit secrets dir:", dir(st.secrets))

# Výpis všech dostupných klíčů v secrets
print("\nAvailable secret keys:")
for key in st.secrets:
    print(f"- {key}")

# Pokus o přečtení secrets.toml přímo
try:
    with open('.streamlit/secrets.toml', 'r') as f:
        print("\nRaw contents of secrets.toml:")
        print(f.read())
except Exception as e:
    print(f"Error reading secrets.toml: {e}")

# Pokus o přístup k secrets
try:
    print("\nTrying to access secrets:")
    if hasattr(st.secrets, 'snowflake'):
        print("Snowflake config found")
        print(f"User: {st.secrets.snowflake.user}")
    if hasattr(st.secrets, 'app_password'):
        print("App password found")
except Exception as e:
    print(f"Error accessing secrets: {e}")

print("=== DEBUG INFO END ===")

# Konfigurace připojení k Snowflake
def init_connection():
    try:
        return connect(
            user=st.secrets["snowflake"]["user"],
            password=st.secrets["snowflake"]["password"],
            account=st.secrets["snowflake"]["account"],
            warehouse=st.secrets["snowflake"]["warehouse"],
            database='STREAMLIT',
            schema='SPA_STUDIO'
        )
    except Exception as e:
        st.error(f"Chyba při připojení k Snowflake: {e}")
        return None

# Funkce pro načtení dat
def load_data(conn, is_completed=False):
    if conn is None:
        return pd.DataFrame(), pd.DataFrame()
    
    try:
        # Načtení prodejních zakázek
        sales_query = f"""
        SELECT * FROM SALES_ORDERS 
        WHERE IS_COMPLETED = {is_completed}
        ORDER BY DATE_CREATED DESC
        """
        sales_df = pd.read_sql(sales_query, conn)
        
        # Načtení servisních zakázek
        service_query = f"""
        SELECT * FROM SERVICE_ORDERS 
        WHERE IS_COMPLETED = {is_completed}
        ORDER BY DATE_CREATED DESC
        """
        service_df = pd.read_sql(service_query, conn)
        
        return sales_df, service_df
    except Exception as e:
        st.error(f"Chyba při načítání dat: {e}")
        return pd.DataFrame(), pd.DataFrame()

# Funkce pro aktualizaci dat
def update_order(conn, table_name, order_id, updates):
    if conn is None:
        return False
    
    try:
        update_cols = ", ".join([f"{k} = %s" for k in updates.keys()])
        id_col = 'SAL_HEAD_ID' if table_name == 'SALES_ORDERS' else 'SRV_HEAD_ID'
        
        query = f"""
        UPDATE {table_name}
        SET {update_cols}, LAST_UPDATE_TIMESTAMP = CURRENT_TIMESTAMP()
        WHERE {id_col} = %s
        """
        
        with conn.cursor() as cur:
            cur.execute(query, list(updates.values()) + [order_id])
            conn.commit()
        return True
    except Exception as e:
        st.error(f"Chyba při aktualizaci dat: {e}")
        return False

# Nastavení stránky
st.set_page_config(page_title="Správa Zakázek", layout="wide")
st.title("Správa Zakázek")

# Přihlášení
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    password = st.text_input("Zadejte přístupové heslo:", type="password")
    try:
        correct_password = st.secrets["snowflake"]["app_password"] 
        if password == correct_password:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Nesprávné heslo")
    except Exception as e:
        st.error(f"Chyba při ověřování hesla: {e}")
        print(f"Error details: {e}")
    st.stop()

# Hlavní aplikace
if st.session_state.authenticated:
    conn = init_connection()
    
    # Přepínač mezi aktivními a dokončenými zakázkami
    show_completed = st.sidebar.checkbox("Zobrazit dokončené zakázky")
    
    # Načtení dat
    sales_df, service_df = load_data(conn, show_completed)
    
    # Záložky pro prodejní a servisní zakázky
    tab1, tab2 = st.tabs(["Prodejní zakázky", "Servisní zakázky"])
    
    with tab1:
        st.header("Prodejní zakázky")
        if not sales_df.empty:
            for _, row in sales_df.iterrows():
                with st.expander(f"Zakázka {row['SAL_HEAD_ID']} - {row['ITEM']}"):
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.write(f"Zákazník: {row['CUST']}")
                        st.write(f"Datum vytvoření: {row['DATE_CREATED']}")
                        st.write(f"Termín realizace: {row['REALISATION_DATE']}")
                    
                    with col2:
                        realized = st.checkbox(
                            "Realizováno",
                            key=f"real_{row['SAL_HEAD_ID']}",
                            value=row['IS_REALIZED']
                        )
                        contacted = st.checkbox(
                            "Zákazník kontaktován",
                            key=f"cont_{row['SAL_HEAD_ID']}",
                            value=row['CUSTOMER_CONTACTED']
                        )
                    
                    with col3:
                        additional_sales = st.number_input(
                            "Dodatečný prodej (Kč)",
                            key=f"sales_{row['SAL_HEAD_ID']}",
                            value=float(row['ADDITIONAL_SALES']),
                            step=100.0
                        )
                        completed = st.checkbox(
                            "Označit jako dokončené",
                            key=f"comp_{row['SAL_HEAD_ID']}",
                            value=row['IS_COMPLETED']
                        )
                    
                    if st.button("Uložit změny", key=f"save_{row['SAL_HEAD_ID']}"):
                        updates = {
                            'IS_REALIZED': realized,
                            'CUSTOMER_CONTACTED': contacted,
                            'ADDITIONAL_SALES': additional_sales,
                            'IS_COMPLETED': completed
                        }
                        if update_order(conn, 'SALES_ORDERS', row['SAL_HEAD_ID'], updates):
                            st.success("Změny byly uloženy")
                            st.rerun()
        else:
            st.info("Žádné prodejní zakázky k zobrazení")
    
    with tab2:
        st.header("Servisní zakázky")
        if not service_df.empty:
            for _, row in service_df.iterrows():
                with st.expander(f"Zakázka {row['SRV_HEAD_ID']} - {row['ITEM']}"):
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.write(f"Zákazník: {row['CUST']}")
                        st.write(f"Datum vytvoření: {row['DATE_CREATED']}")
                        st.write(f"Termín realizace: {row['REALISATION_DATE']}")
                    
                    with col2:
                        realized = st.checkbox(
                            "Realizováno",
                            key=f"real_{row['SRV_HEAD_ID']}",
                            value=row['IS_REALIZED']
                        )
                        contacted = st.checkbox(
                            "Zákazník kontaktován",
                            key=f"cont_{row['SRV_HEAD_ID']}",
                            value=row['CUSTOMER_CONTACTED']
                        )
                    
                    with col3:
                        additional_sales = st.number_input(
                            "Dodatečný prodej (Kč)",
                            key=f"sales_{row['SRV_HEAD_ID']}",
                            value=float(row['ADDITIONAL_SALES']),
                            step=100.0
                        )
                        completed = st.checkbox(
                            "Označit jako dokončené",
                            key=f"comp_{row['SRV_HEAD_ID']}",
                            value=row['IS_COMPLETED']
                        )
                    
                    if st.button("Uložit změny", key=f"save_{row['SRV_HEAD_ID']}"):
                        updates = {
                            'IS_REALIZED': realized,
                            'CUSTOMER_CONTACTED': contacted,
                            'ADDITIONAL_SALES': additional_sales,
                            'IS_COMPLETED': completed
                        }
                        if update_order(conn, 'SERVICE_ORDERS', row['SRV_HEAD_ID'], updates):
                            st.success("Změny byly uloženy")
                            st.rerun()
        else:
            st.info("Žádné servisní zakázky k zobrazení")