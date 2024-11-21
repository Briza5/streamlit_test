import streamlit as st
import pandas as pd
from snowflake.connector import connect
import datetime
import os
from datetime import datetime
import csv
from io import StringIO

# Debug informace
print("=== DEBUG INFO START ===")
print("Current working directory:", os.getcwd())
print("Streamlit secrets type:", type(st.secrets))
print("Streamlit secrets dir:", dir(st.secrets))

# Výpis dostupných klíčů v secrets
print("\nAvailable secret keys:")
for key in st.secrets:
   print(f"- {key}")

# Pokus o přečtení secrets.toml
try:
   with open('.streamlit/secrets.toml', 'r') as f:
       print("\nRaw contents of secrets.toml:")
       print(f.read())
except Exception as e:
   print(f"Error reading secrets.toml: {e}")

print("=== DEBUG INFO END ===")

def format_currency(value, company):
   """Formátování měny podle společnosti"""
   if company == "SKMF":
       return f"{value:,.2f} €"
   return f"{value:,.2f} Kč"

def init_connection():
   try:
       with st.spinner('Připojování k databázi...'):
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

def create_filters():
   with st.sidebar:
       st.header("Filtry")
       filters = {}
       filters['item'] = st.text_input("Filtr dle typu zboží")
       filters['order_id'] = st.text_input("Filtr dle čísla zakázky")
       filters['cust'] = st.text_input("Filtr dle zákazníka")
       col1, col2 = st.columns(2)
       with col1:
           filters['date_from'] = st.date_input("Datum vytvoření od")
       with col2:
           filters['date_to'] = st.date_input("Datum vytvoření do")
       filters['min_sales'] = st.number_input("Min. dodatečný prodej", min_value=0)
       filters['contacted'] = st.selectbox("Kontaktován", ['Vše', 'Ano', 'Ne'])
       filters['realized'] = st.selectbox("Realizováno", ['Vše', 'Ano', 'Ne'])
       return filters

def apply_filters(df, filters):
    if df.empty:
        return df
    
    # Převod datumových sloupců na správný formát
    df['DATE_CREATED'] = pd.to_datetime(df['DATE_CREATED'], format='%d.%m.%Y')
    df['REALISATION_DATE'] = pd.to_datetime(df['REALISATION_DATE'], format='%d.%m.%Y')
    
    if filters.get('use_item') and filters.get('item'):
        df = df[df['ITEM'].str.contains(filters['item'], case=False, na=False)]
        
    if filters.get('use_order') and filters.get('order_id'):
        id_col = 'SAL_HEAD_ID' if 'SAL_HEAD_ID' in df.columns else 'SRV_HEAD_ID'
        df = df[df[id_col].str.contains(filters['order_id'], case=False, na=False)]
        
    if filters.get('use_customer') and filters.get('cust'):
        df = df[df['CUST'].str.contains(filters['cust'], case=False, na=False)]
        
    if filters.get('use_date_created'):
        if filters.get('date_from'):
            df = df[df['DATE_CREATED'].dt.date >= filters['date_from']]
        if filters.get('date_to'):
            df = df[df['DATE_CREATED'].dt.date <= filters['date_to']]
            
    if filters.get('use_date_realisation'):
        if filters.get('real_date_from'):
            df = df[df['REALISATION_DATE'].dt.date >= filters['real_date_from']]
        if filters.get('real_date_to'):
            df = df[df['REALISATION_DATE'].dt.date <= filters['real_date_to']]
            
    if filters.get('use_sales') and filters.get('min_sales', 0) > 0:
        df = df[df['ADDITIONAL_SALES'] >= filters['min_sales']]
        
    if filters.get('use_status'):
        if filters.get('contacted') != 'Vše':
            df = df[df['CUSTOMER_CONTACTED'] == (filters['contacted'] == 'Ano')]
        if filters.get('realized') != 'Vše':
            df = df[df['IS_REALIZED'] == (filters['realized'] == 'Ano')]
    
    # Převod datumů zpět na string pro zobrazení
    df['DATE_CREATED'] = df['DATE_CREATED'].dt.strftime('%d.%m.%Y')
    df['REALISATION_DATE'] = df['REALISATION_DATE'].dt.strftime('%d.%m.%Y')
            
    return df

def load_data(conn, is_completed=False):
   if conn is None:
       return pd.DataFrame(), pd.DataFrame()
   
   try:
       with st.spinner('Načítání dat...'):
           sales_query = f"""
           SELECT * FROM SALES_ORDERS 
           WHERE IS_COMPLETED = {is_completed}
           ORDER BY DATE_CREATED DESC
           """
           sales_df = pd.read_sql(sales_query, conn)
           
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

def export_to_csv(df, filename):
   """Export dataframe do CSV"""
   csv = df.to_csv(index=False).encode('utf-8')
   st.download_button(
       "Stáhnout CSV",
       csv,
       filename,
       "text/csv",
       key='download-csv'
   )

def show_statistics(df, title):
   """Zobrazení statistik"""
   st.subheader(f"Statistiky - {title}")
   col1, col2, col3, col4 = st.columns(4)
   with col1:
       st.metric("Počet zakázek", len(df))
   with col2:
       st.metric("Realizované zakázky", len(df[df['IS_REALIZED']]))
   with col3:
       st.metric("Kontaktovaní zákazníci", len(df[df['CUSTOMER_CONTACTED']]))
   with col4:
       total_sales = df['ADDITIONAL_SALES'].sum()
       st.metric("Celkové dodatečné prodeje", f"{total_sales:,.2f} Kč")

def show_order_details(row, order_type):
   """Zobrazení detailů zakázky"""
   table_name = 'SALES_ORDERS' if order_type == 'sales' else 'SERVICE_ORDERS'
   id_col = 'SAL_HEAD_ID' if order_type == 'sales' else 'SRV_HEAD_ID'
   
   col1, col2, col3 = st.columns(3)
   
   with col1:
       st.write(f"Zákazník: {row['CUST']}")
       st.write(f"Datum vytvoření: {pd.to_datetime(row['DATE_CREATED']).strftime('%d.%m.%Y')}")
       st.write(f"Termín realizace: {pd.to_datetime(row['REALISATION_DATE']).strftime('%d.%m.%Y')}")
   
   with col2:
       realized = st.checkbox(
           "Realizováno",
           key=f"real_{row[id_col]}",
           value=row['IS_REALIZED']
       )
       contacted = st.checkbox(
           "Zákazník kontaktován",
           key=f"cont_{row[id_col]}",
           value=row['CUSTOMER_CONTACTED']
       )
   
   with col3:
       additional_sales = st.number_input(
           "Dodatečný prodej (Kč)",
           key=f"sales_{row[id_col]}",
           value=float(row['ADDITIONAL_SALES']),
           step=100.0
       )
       
       # Pole pro poznámky
       notes = st.text_area(
           "Poznámky",
           value=row.get('NOTES', ''),
           key=f"notes_{row[id_col]}"
       )
   
   # Tlačítko pro označení jako dokončené s potvrzovacím dialogem
   if st.checkbox("Označit jako dokončené", key=f"comp_{row[id_col]}", value=row['IS_COMPLETED']):
       if st.button("Potvrdit dokončení", key=f"confirm_{row[id_col]}"):
           completed = True
       else:
           st.warning("Potvrďte prosím dokončení zakázky")
           completed = False
   else:
       completed = False
   
   if st.button("Uložit změny", key=f"save_{row[id_col]}"):
       updates = {
           'IS_REALIZED': realized,
           'CUSTOMER_CONTACTED': contacted,
           'ADDITIONAL_SALES': additional_sales,
           'IS_COMPLETED': completed,
           'NOTES': notes
       }
       if update_order(conn, table_name, row[id_col], updates):
           st.success("Změny byly uloženy")
           st.rerun()

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
   
   # Filtry
   filters = create_filters()
   sort_by = st.sidebar.selectbox(
       "Seřadit dle",
       ['Datum vytvoření ↑', 'Datum vytvoření ↓', 'Termín realizace ↑', 'Termín realizace ↓']
   )
   
   # Načtení dat
   with st.spinner('Načítání dat...'):
       sales_df, service_df = load_data(conn, show_completed)
   
   # Záložky pro prodejní a servisní zakázky
   tab1, tab2 = st.tabs(["Prodejní zakázky", "Servisní zakázky"])
   
   with tab1:
       st.header("Prodejní zakázky")
       if not sales_df.empty:
           filtered_df = apply_filters(sales_df, filters)
           
           # Statistiky
           show_statistics(filtered_df, "Prodejní zakázky")
           
           # Export do CSV
           export_to_csv(filtered_df, "prodejni_zakazky.csv")
           
           # Seřazení
           sort_col = 'DATE_CREATED' if 'vytvoření' in sort_by else 'REALISATION_DATE'
           ascending = '↑' in sort_by
           filtered_df = filtered_df.sort_values(sort_col, ascending=ascending)
           
           st.write(f"Zobrazeno {len(filtered_df)} z {len(sales_df)} zakázek")
           
           for _, row in filtered_df.iterrows():
               with st.expander(
                   f"[{row['SAL_HEAD_ID']}] {row['CUST']} - {row['ITEM']} "
                   f"(Vytvořeno: {pd.to_datetime(row['DATE_CREATED']).strftime('%d.%m.%Y')}, "
                   f"Realizace: {pd.to_datetime(row['REALISATION_DATE']).strftime('%d.%m.%Y')})"
               ):
                   show_order_details(row, 'sales')
       else:
           st.info("Žádné prodejní zakázky k zobrazení")
   
   with tab2:
       st.header("Servisní zakázky")
       if not service_df.empty:
           filtered_df = apply_filters(service_df, filters)
           
           # Statistiky
           show_statistics(filtered_df, "Servisní zakázky")
           
           # Export do CSV
           export_to_csv(filtered_df, "servisni_zakazky.csv")
           
           # Seřazení
           sort_col = 'DATE_CREATED' if 'vytvoření' in sort_by else 'REALISATION_DATE'
           ascending = '↑' in sort_by
           filtered_df = filtered_df.sort_values(sort_col, ascending=ascending)
           
           st.write(f"Zobrazeno {len(filtered_df)} z {len(service_df)} zakázek")
           
           for _, row in filtered_df.iterrows():
               with st.expander(
                   f"[{row['SRV_HEAD_ID']}] {row['CUST']} - {row['ITEM']} "
                   f"(Vytvořeno: {pd.to_datetime(row['DATE_CREATED']).strftime('%d.%m.%Y')}, "
                   f"Realizace: {pd.to_datetime(row['REALISATION_DATE']).strftime('%d.%m.%Y')})"
               ):
                   show_order_details(row, 'service')
       else:
           st.info("Žádné servisní zakázky k zobrazení")