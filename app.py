import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup

# --- CONFIGURATION & SETUP ---
st.set_page_config(page_title="High-Value B2B Lead Engine", page_icon="🏢", layout="wide")

st.title("🏢 Dual-Engine B2B Real Estate Lead Pipeline")
st.markdown("Automated aggregation from **RapidAPI (MLS)** and **Custom Web Scraping (Crexi)**.")

# --- SECRETS MANAGEMENT ---
try:
    RAPIDAPI_KEY = st.secrets["RAPIDAPI_KEY"]
except KeyError:
    st.error("⚠️ Critical Error: RapidAPI key missing in Streamlit Cloud Secrets.")
    st.stop()

# --- ENGINE 1: RAPIDAPI (MLS RETAIL) ---
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_rapidapi_data(location, min_price):
    url = "https://real-time-real-estate-data.p.rapidapi.com/search"
    querystring = {"location": location, "sort": "NEWEST"}
    headers = {"X-RapidAPI-Key": RAPIDAPI_KEY, "X-RapidAPI-Host": "real-time-real-estate-data.p.rapidapi.com"}
    
    try:
        response = requests.get(url, headers=headers, params=querystring, timeout=15)
        if response.status_code != 200: 
            st.error(f"🔴 RapidAPI Failed: [Status {response.status_code}] {response.text}")
            return pd.DataFrame()
            
        data = response.json()
        listings = data.get("data", {}).get("listings", []) if isinstance(data, dict) else []
        
        leads = []
        for item in listings:
            price = item.get("price", 0)
            if isinstance(price, str): 
                price = int(''.join(filter(str.isdigit, price))) if any(c.isdigit() for c in price) else 0

            if price >= min_price:
                leads.append({
                    "Source": "RapidAPI (MLS)",
                    "Lead ID": f"RA-{item.get('zpid', '0000')}",
                    "Address": item.get("address", "N/A"),
                    "City": item.get("city", ""),
                    "State": item.get("state", ""),
                    "Property Type": item.get("homeType", "N/A"),
                    "Price ($)": price
                })
        return pd.DataFrame(leads)
    except Exception as e:
        st.error(f"🔴 RapidAPI Python Error: {e}")
        return pd.DataFrame()

# --- ENGINE 2: CUSTOM WEB SCRAPER (CREXI) ---
@st.cache_data(ttl=3600, show_spinner=False)
def scrape_crexi_directory(city, state, min_price):
    # Format city for URL (e.g., "Austin" -> "austin")
    formatted_city = city.lower().replace(" ", "-")
    formatted_state = state.lower()
    
    # Target Crexi's public search directory
    url = f"https://www.crexi.com/properties?locations={formatted_city}%2C%20{formatted_state}"
    
    # Heavy camouflage to bypass basic bot blockers
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Referer": "https://www.google.com/"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        # If Crexi's firewall blocks us, it usually returns 403 Forbidden
        if response.status_code != 200:
            st.warning(f"⚠️ Crexi Scraper Blocked: Server returned status {response.status_code}. Anti-bot protection active.")
            return pd.DataFrame()
            
        soup = BeautifulSoup(response.text, "html.parser")
        leads = []
        
        # Target general property card structures (Crexi UI classes update frequently)
        listings = soup.find_all("div", class_=lambda value: value and "property" in value.lower())
        
        for idx, item in enumerate(listings):
            try:
                # Scan card for price indicators
                price_elem = item.find(string=lambda t: t and "$" in t)
                if not price_elem: continue
                
                price_text = price_elem.strip()
                price = int(''.join(filter(str.isdigit, price_text)))
                
                if price >= min_price:
                    # Attempt to pull address mapping
                    address_elem = item.find("div", class_=lambda value: value and "address" in value.lower())
                    address = address_elem.text.strip() if address_elem else "Undisclosed Location"
                    
                    leads.append({
                        "Source": "Scraper (Crexi)",
                        "Lead ID": f"CX-{str(idx).zfill(4)}",
                        "Address": address,
                        "City": city.title(),
                        "State": state.upper(), 
                        "Property Type": "Commercial",
                        "Price ($)": price
                    })
            except Exception:
                continue
                
        return pd.DataFrame(leads)
    except Exception as e:
        st.warning(f"⚠️ Crexi Scraper Logic Error: {e}")
        return pd.DataFrame()

# --- SIDEBAR & UX CONTROLS ---
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
    
    with st.spinner(f"Running Dual-Engine extraction for {target_city}, {target_state}..."):
        
        rapidapi_df = fetch_rapidapi_data(f"{target_city}, {target_state}", min_price_threshold)
        scraper_df = scrape_crexi_directory(target_city, target_state, min_price_threshold)
        
        combined_df = pd.concat([rapidapi_df, scraper_df], ignore_index=True)
        
        if combined_df.empty:
            st.warning("⚠️ No properties matched your city/state/price criteria.")
        else:
            combined_df = combined_df.drop_duplicates(subset=["Address"]).sort_values(by="Price ($)", ascending=False)
            
            # --- EXECUTIVE METRICS ---
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Qualified Leads", len(combined_df))
            col2.metric("Pipeline Value", f"${int(combined_df['Price ($)'].sum()):,}")
            col3.metric("Avg Property Value", f"${int(combined_df['Price ($)'].mean()):,}")
            
            # --- TABS ---
            st.markdown("### Actionable B2B Directory")
            tab1, tab2, tab3 = st.tabs(["📊 Master", "🌐 RapidAPI", "🏢 Scraped (Crexi)"])
            
            with tab1:
                st.dataframe(combined_df.style.format({"Price ($)": "${:,.0f}"}), use_container_width=True)
            with tab2:
                st.dataframe(combined_df[combined_df["Source"] == "RapidAPI (MLS)"].style.format({"Price ($)": "${:,.0f}"}), use_container_width=True)
            with tab3:
                st.dataframe(combined_df[combined_df["Source"] == "Scraper (Crexi)"].style.format({"Price ($)": "${:,.0f}"}), use_container_width=True)
else:
    st.info("👈 Set your parameters and click **Run Lead Generation**.")
