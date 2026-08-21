import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup

# --- CONFIGURATION & SETUP ---
st.set_page_config(page_title="High-Value B2B Lead Engine", page_icon="🏢", layout="wide")

st.markdown("""
    <style>
    .stDataFrame { border-radius: 8px; overflow: hidden; }
    </style>
""", unsafe_allow_html=True)

st.title("🏢 Tri-Engine B2B Real Estate Lead Pipeline")
st.markdown("Automated aggregation from **RentCast**, **RapidAPI (MLS)**, and **Custom Web Scraping**.")

# --- SECRETS MANAGEMENT ---
try:
    RENTCAST_KEY = st.secrets["RENTCAST_API_KEY"]
    RAPIDAPI_KEY = st.secrets["RAPIDAPI_KEY"]
except KeyError:
    st.error("⚠️ Critical Error: API keys missing in Streamlit Cloud Secrets.")
    st.stop()

# --- ENGINE 1: RENTCAST API ---
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_rentcast_data(city, state, min_price):
    url = "https://api.rentcast.io/v1/listings/sale"
    params = {"city": city, "state": state, "limit": 100, "status": "Active"}
    headers = {"accept": "application/json", "X-Api-Key": RENTCAST_KEY}
    
    try:
        response = requests.get(url, params=params, headers=headers, timeout=15)
        if response.status_code != 200: return pd.DataFrame()
        
        leads = []
        for item in response.json():
            price = item.get("price", 0)
            if price >= min_price:
                leads.append({
                    "Source": "RentCast API",
                    "Lead ID": f"RC-{str(item.get('id', '00'))[-6:]}",
                    "Address": item.get("addressLine1", "N/A"),
                    "City": item.get("city", ""),
                    "State": item.get("state", ""),
                    "Property Type": item.get("propertyType", "N/A"),
                    "Price ($)": price
                })
        return pd.DataFrame(leads)
    except Exception:
        return pd.DataFrame()

# --- ENGINE 2: RAPIDAPI (MLS RETAIL) ---
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_rapidapi_data(location, min_price):
    url = "https://real-time-real-estate-data.p.rapidapi.com/search"
    querystring = {"location": location, "sort": "newest"}
    headers = {"X-RapidAPI-Key": RAPIDAPI_KEY, "X-RapidAPI-Host": "real-time-real-estate-data.p.rapidapi.com"}
    
    try:
        response = requests.get(url, headers=headers, params=querystring, timeout=15)
        if response.status_code != 200: return pd.DataFrame()
            
        data = response.json()
        listings = data.get("data", {}).get("listings", []) if isinstance(data, dict) else []
        
        leads = []
        for item in listings:
            price = item.get("price", 0)
            if isinstance(price, str): price = int(''.join(filter(str.isdigit, price))) if any(c.isdigit() for c in price) else 0

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
    except Exception:
        return pd.DataFrame()

# --- ENGINE 3: CUSTOM WEB SCRAPER ---
@st.cache_data(ttl=3600, show_spinner=False)
def scrape_off_market_directory(city, min_price):
    """
    Template for scraping local directories. 
    Update the URL and soup.find() classes to match your target website's HTML structure.
    """
    url = f"https://www.example-commercial-real-estate.com/search?city={city}"
    # Using a User-Agent header is a standard practice to identify your scraper and prevent immediate blocking by simple bot protections.
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code != 200: return pd.DataFrame()
            
        soup = BeautifulSoup(response.text, "html.parser")
        leads = []
        
        # Replace 'listing-card' with the actual HTML class from your target site
        listings = soup.find_all("div", class_="listing-card")
        
        for idx, item in enumerate(listings):
            try:
                # Replace 'price-text' and 'address-text' with actual HTML classes
                price_text = item.find("span", class_="price-text").text
                price = int(''.join(filter(str.isdigit, price_text)))
                
                if price >= min_price:
                    leads.append({
                        "Source": "Scraper (Off-Market)",
                        "Lead ID": f"WS-{str(idx).zfill(4)}",
                        "Address": item.find("h3", class_="address-text").text.strip(),
                        "City": city,
                        "State": "N/A", 
                        "Property Type": "Commercial/Unlisted",
                        "Price ($)": price
                    })
            except AttributeError:
                # Skips cards that are missing price or address data
                continue
                
        return pd.DataFrame(leads)
    except Exception as e:
        return pd.DataFrame()

# --- SIDEBAR & UX CONTROLS ---
with st.sidebar:
    st.header("⚙️ Target Parameters")
    target_city = st.text_input("Target City", value="Austin")
    target_state = st.text_input("Target State (2-letter)", value="TX", max_chars=2)
    min_price_threshold = st.number_input("Minimum Value ($)", min_value=100000, value=1850000, step=50000)
    st.markdown("---")
    execute_search = st.button("🚀 Run Lead Generation", use_container_width=True)

# --- EXECUTION PIPELINE ---
if execute_search:
    with st.spinner(f"Running Tri-Engine extraction for {target_city}, {target_state}..."):
        
        # Execute all three data streams
        rentcast_df = fetch_rentcast_data(target_city, target_state, min_price_threshold)
        rapidapi_df = fetch_rapidapi_data(f"{target_city}, {target_state}", min_price_threshold)
        scraper_df = scrape_off_market_directory(target_city, min_price_threshold)
        
        # Merge all datasets
        combined_df = pd.concat([rentcast_df, rapidapi_df, scraper_df], ignore_index=True)
        
        if combined_df.empty:
            st.warning("No properties found. Try adjusting criteria.")
        else:
            # Deduplicate across all three sources to ensure a clean list
            combined_df = combined_df.drop_duplicates(subset=["Address"]).sort_values(by="Price ($)", ascending=False)
            
            # --- EXECUTIVE METRICS ---
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Qualified Leads", len(combined_df))
            col2.metric("Pipeline Value", f"${int(combined_df['Price ($)'].sum()):,}")
            col3.metric("Avg Property Value", f"${int(combined_df['Price ($)'].mean()):,}")
            
            # --- TABS ---
            st.markdown("### Actionable B2B Directory")
            tab1, tab2, tab3, tab4 = st.tabs(["📊 Master", "🏠 RentCast", "🌐 RapidAPI", "🕷️ Scraped"])
            
            with tab1:
                st.dataframe(combined_df.style.format({"Price ($)": "${:,.0f}"}), use_container_width=True)
            with tab2:
                st.dataframe(combined_df[combined_df["Source"] == "RentCast API"].style.format({"Price ($)": "${:,.0f}"}), use_container_width=True)
            with tab3:
                st.dataframe(combined_df[combined_df["Source"] == "RapidAPI (MLS)"].style.format({"Price ($)": "${:,.0f}"}), use_container_width=True)
            with tab4:
                st.dataframe(combined_df[combined_df["Source"] == "Scraper (Off-Market)"].style.format({"Price ($)": "${:,.0f}"}), use_container_width=True)

else:
    st.info("👈 Set your parameters and click **Run Lead Generation**.")
