import streamlit as st
import pandas as pd
import random

st.set_page_config(page_title="High-Value B2B Lead Engine", layout="wide")
st.title("🏙️ High-Value B2B Real Estate Lead Engine")
st.write("Real-time automated lead extraction and verified property filtering.")

# 1. Dynamic Scale Data Generator (Simulates Live API Ingestion)
@st.cache_data
def generate_b2b_leads(num_leads=120):
    random.seed(42)
    
    property_types = [
        "Prime Commercial Office", "Multi-Family Unit", "Industrial Warehouse", 
        "Retail Storefront", "Off-Market Land", "Logistics Hub", "Medical Center"
    ]
    cities = ["Austin, TX", "Miami, FL", "Dallas, TX", "Atlanta, GA", "Phoenix, AZ", "Denver, CO", "Seattle, WA"]
    statuses = ["Verified", "Pending", "Unverified"]
    first_names = ["Marcus", "Elena", "Devon", "Sarah", "James", "Aaliyah", "Chen", "Sofia"]
    last_names = ["Vance", "Reyes", "Sterling", "O'Connor", "Zhao", "Patel", "Wright"]
    
    leads = []
    for i in range(1, num_leads + 1):
        price = random.randint(150, 2500) * 1000
        city = random.choice(cities)
        status = random.choice(statuses)
        owner = f"{random.choice(first_names)} {random.choice(last_names)}"
        email = f"{owner.lower().replace(' ', '.')}@investments.com"
        
        leads.append({
            "Lead ID": f"B2B-{1000 + i}",
            "Property Title": f"{random.choice(property_types)} {i}",
            "Price ($)": price,
            "Location": city,
            "Owner / Contact": owner,
            "Email": email,
            "Verification Status": status
        })
    return pd.DataFrame(leads)

df = generate_b2b_leads()

# 2. Sidebar Controls
st.sidebar.header("Filter Criteria")
location_search = st.sidebar.text_input("🔍 Search Location (e.g., Austin, TX or Miami):", value="")
min_price = st.sidebar.slider("Minimum Property Price ($)", 100000, 2500000, 500000, step=50000)
only_verified = st.sidebar.checkbox("Show Only Verified Contacts", value=True)

# 3. Dynamic Filter Logic
filtered_df = df[
    (df["Price ($)"] >= min_price) & 
    (df["Location"].str.contains(location_search, case=False, na=False))
]

if only_verified:
    filtered_df = filtered_df[filtered_df["Verification Status"] == "Verified"]

# 4. Executive Metrics
col1, col2, col3 = st.columns(3)
col1.metric("Total Qualified Leads", len(filtered_df))
col2.metric("Highest Listed Value", f"${filtered_df['Price ($)'].max():,}" if not filtered_df.empty else "$0")
col3.metric("Avg Property Value", f"${int(filtered_df['Price ($)'].mean()):,}" if not filtered_df.empty else "$0")

# 5. Interactive Data Table & Export
st.subheader("Actionable Lead Directory")
st.dataframe(filtered_df, use_container_width=True)

csv = filtered_df.to_csv(index=False).encode('utf-8')
st.download_button(
    "📥 Export Filtered Leads to CSV", 
    data=csv, 
    file_name="b2b_real_estate_leads.csv", 
    mime="text/csv"
)
