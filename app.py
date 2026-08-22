import streamlit as st
import pandas as pd
import requests
import re
from bs4 import BeautifulSoup

# --- CONFIGURATION & SETUP ---
st.set_page_config(page_title="High-Value B2B Lead Engine", page_icon="🏢", layout="wide")

st.title("🏢 Dual-Engine B2B Real Estate Lead Pipeline")
st.markdown("Automated aggregation from **RapidAPI (MLS)** and **Custom Web Scraping (Open Directories)**.")

# --- SANITIZATION HELPER ---
def sanitize_input(text):
    """Strips emojis, special characters, and extra spaces to prevent API breaks."""
    return re.sub(r'[^a-zA-Z\s]', '', str(text)).strip()

# --- SECRETS MANAGEMENT ---
try:
    RAPIDAPI_KEY = st.secrets["RAPIDAPI_KEY"]
except KeyError:
    st.error("⚠️ Critical Error: RapidAPI key missing in Streamlit Cloud Secrets.")
    st.stop()

# --- ENGINE 1: RAPIDAPI (MLS RETAIL) ---
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_rapidapi_data(city, state, min_price):
    clean_city = sanitize_input(city)
    clean_state = sanitize_input(state)[:2].upper()
    location = f"{clean_city}, {clean_state}"
    
    url = "https://real-time-real-estate-data.p.rapidapi.com/search"
    querystring = {"location": location, "sort": "NEWEST"}
    headers = {"X-RapidAPI-Key": RAPIDAPI_KEY, "X-RapidAPI-Host": "real-time-real-estate-data.p.rapidapi.com"}
    
    try:
        response = requests.get(url, headers=headers, params=querystring, timeout=15)
        if response.status_code != 200: 
            st.error(f"🔴 RapidAPI Failed: [Status {response.status_code}] {response.text}")
            return pd.DataFrame()
            
        data = response.json()
        data_payload = data.get("data", [])
        
        if isinstance(data_payload, dict):
            listings = data_payload.get("listings", [])
        elif isinstance(data_payload, list):
            listings = data_payload
        else:
            listings = []
            
        leads = []
        for item in listings:
            price = item.get("price", 0)
            if isinstance(price, str): 
                price = int(''.join(filter(str.isdigit, price))) if any(c.isdigit() for c in price) else 0

            if price >= min_price:
                leads.append({
                    "Source": "RapidAPI (MLS)",
                    "Lead ID": f"RA-{item.get('zpid', item.get('id', '0000'))}",
                    "Address": item.get("address", item.get("streetAddress", "N/A")),
                    "City": item.get("city", clean_city),
                    "State": item.get("state", clean_state),
                    "Property Type": item.get("homeType", item.get("propertyType", "N/A")),
                    "Price ($)": price
                })
        return pd.DataFrame(leads)
    except Exception as e:
        st.error(f"🔴 RapidAPI Python Error: {e}")
        return pd.DataFrame()

# --- ENGINE 2: CUSTOM WEB SCRAPER (OPEN DIRECTORY) ---
@st.cache_data(ttl=3600, show_spinner=False)
def scrape_open_directory(city, min_price):
    clean_city = sanitize_input(city).replace(" ", "+")
    url = f"https://totalcommercial.com/listings?q={clean_city}"
    headers = {"User-Agent": "Mozilla/5.0"}
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code != 200: return pd.DataFrame()
            
        soup = BeautifulSoup(response.text, "html.parser")
        leads = []
        listings = soup.find_all("div", class_="listing") 
        
        for idx, item in enumerate(listings):
            try:
                price_text = item.text
                if "$" in price_text:
                    raw_price = price_text.split("$")[1].split(" ")[0].split("\n")[0]
                    price = int(''.join(filter(str.isdigit, raw_price)))
                    
                    if price >= min_price:
                        leads.append({
                            "Source": "Scraper (TotalCommercial)",
                            "Lead ID": f"TC-{str(idx).zfill(4)}",
                            "Address": "Available on Directory",
                            "City": sanitize_input(city).title(),
                            "State": "N/A", 
                            "Property Type": "Commercial",
                            "Price ($)": price
                        })
            except Exception:
                continue
                
        return pd.DataFrame(leads)
    except Exception:
        return pd.DataFrame()

# --- SIDEBAR & CONTROLS ---
with st.sidebar:
    st.header("⚙️ Target Parameters")
    target_city = st.text_input("Target City", value="Austin")
    target_state = st.text_input("Target State (2-letter)", value="TX", max_chars=2)
    min_price_threshold = st.number_input("Minimum Value ($)", min_value=10000, value=100000, step=50000)
    st.markdown("---")
    execute_search = st.button("🚀 Run Lead Generation", use_container_width=True)

# --- EXECUTION PIPELINE ---
if execute_search:
    st.cache_data.clear() 
    
    with st.spinner(f"Running Dual-Engine extraction..."):
        rapidapi_df = fetch_rapidapi_data(target_city, target_state, min_price_threshold)
        scraper_df = scrape_open_directory(target_city, min_price_threshold)
        
        combined_df = pd.concat([rapidapi_df, scraper_df], ignore_index=True)
        
        if combined_df.empty:
            st.warning("⚠️ No properties matched your criteria.")
        else:
            combined_df = combined_df.drop_duplicates(subset=["Address"]).sort_values(by="Price ($)", ascending=False)
            
            # Executive Metrics
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Qualified Leads", len(combined_df))
            col2.metric("Pipeline Value", f"${int(combined_df['Price ($)'].sum()):,}")
            col3.metric("Avg Property Value", f"${int(combined_df['Price ($)'].mean()):,}")
            
            # Directory & CSV Export
            st.markdown("### Actionable B2B Directory")
            tab1, tab2, tab3 = st.tabs(["📊 Master", "🌐 RapidAPI", "🏢 Scraped"])
            
            with tab1:
                st.dataframe(combined_df.style.format({"Price ($)": "${:,.0f}"}), use_container_width=True)
                csv_data = combined_df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Export Master Leads to CSV",
                    data=csv_data,
                    file_name=f"{sanitize_input(target_city)}_Leads.csv",
                    mime="text/csv"
                )
            with tab2:
                st.dataframe(combined_df[combined_df["Source"] == "RapidAPI (MLS)"].style.format({"Price ($)": "${:,.0f}"}), use_container_width=True)
            with tab3:
                st.dataframe(combined_df[combined_df["Source"] == "Scraper (TotalCommercial)"].style.format({"Price ($)": "${:,.0f}"}), use_container_width=True)
else:
    st.info("👈 Set your parameters and click **Run Lead Generation**.")
