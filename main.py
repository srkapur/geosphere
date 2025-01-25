import streamlit as st
from geopy.geocoders import Nominatim, GoogleV3
from geopy.exc import GeocoderTimedOut
import pandas as pd
import time
import re
import pycountry

def is_chinese(text):
    # Check if the text contains Chinese characters
    if text is None:
        return False
    return bool(re.search('[\u4e00-\u9fff]', text))

def get_country_list():
    # Get list of countries from pycountry
    countries = [(country.alpha_2, country.name) for country in pycountry.countries]
    countries.sort(key=lambda x: x[1])  # Sort by country name
    return countries

def clean_address(address):
    """Clean and standardize address"""
    # Remove extra spaces and common punctuation
    address = re.sub(r'\s+', ' ', address)
    address = re.sub(r'[,.-]', ' ', address)
    return address.strip()

def get_coordinates(location, country_code=None, api_key=None):
    try:
        original_location = location
        location = clean_address(location)
        
        # Try Google Maps API first if API key is provided
        if api_key:
            geolocator = GoogleV3(api_key=api_key)
            try:
                # Add country bias if specified
                if country_code and country_code != 'GLOBAL':
                    country_name = pycountry.countries.get(alpha_2=country_code).name
                    if country_name.lower() not in location.lower():
                        location = f"{location}, {country_name}"
                
                result = geolocator.geocode(
                    location,
                    exactly_one=True
                )
                
                if result:
                    return {
                        'latitude': result.latitude,
                        'longitude': result.longitude,
                        'address': result.address,
                        'match_level': "GOOGLE_MATCH",
                        'confidence': "High",
                        'original_address': original_location
                    }
            except Exception as e:
                st.warning(f"Google Maps API error: {str(e)}, falling back to Nominatim")
        
        # Fall back to Nominatim if Google fails or no API key
        geolocator = Nominatim(user_agent="my_geocoder_app")
        
        # Try with full address first
        if country_code and country_code != 'GLOBAL':
            country_name = pycountry.countries.get(alpha_2=country_code).name
            search_location = f"{location}, {country_name}"
        else:
            search_location = location
            
        result = geolocator.geocode(
            search_location,
            exactly_one=True,
            language='en',
            country_codes=None if country_code == 'GLOBAL' else [country_code]
        )
        
        if result:
            formatted_address = result.address.replace(", ", "\n")
            return {
                'latitude': result.latitude,
                'longitude': result.longitude,
                'address': formatted_address,
                'match_level': "NOMINATIM_FULL",
                'confidence': "Medium",
                'original_address': original_location
            }
            
        return None
            
    except GeocoderTimedOut:
        return None
    except Exception as e:
        st.error(f"Error processing address: {str(e)}")
        return None

def process_csv(df, address_column, country_code, api_key=None):
    # Add new columns for results
    df['latitude'] = None
    df['longitude'] = None
    df['full_address'] = None
    df['match_level'] = None
    df['confidence'] = None
    
    # Create a progress bar
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    # Process each address
    total_rows = len(df)
    for index, row in df.iterrows():
        status_text.text(f"Processing row {index + 1}/{total_rows}")
        
        # Skip empty addresses
        if pd.isna(row[address_column]) or str(row[address_column]).strip() == '':
            continue
            
        result = get_coordinates(str(row[address_column]), country_code, api_key)
        if result:
            df.at[index, 'latitude'] = result['latitude']
            df.at[index, 'longitude'] = result['longitude']
            df.at[index, 'full_address'] = result['address']
            df.at[index, 'match_level'] = result['match_level']
            df.at[index, 'confidence'] = result['confidence']
        
        # Update progress bar
        progress_bar.progress((index + 1) / total_rows)
        
        # Add a small delay to avoid hitting API limits
        time.sleep(1)
    
    status_text.text("Processing complete!")
    return df

def main():
    st.title("Advanced Address Geocoding App")
    st.write("Convert addresses to latitude and longitude coordinates worldwide")
    
    # Get list of countries
    countries = get_country_list()
    # Add global option at the top
    country_options = [('GLOBAL', 'Global (No country filter)')] + countries
    
    # API Key input in sidebar
    api_key = st.sidebar.text_input(
        "Enter Google Maps API Key (optional):",
        type="password",
        help="Using a Google Maps API key will provide better results"
    )
    
    # Create tabs for single address and CSV processing
    tab1, tab2 = st.tabs(["Single Address", "CSV File"])
    
    # Single Address Tab
    with tab1:
        st.header("Process Single Address")
        
        # Country selection
        selected_country = st.selectbox(
            "Select country (or Global for no filter):",
            options=[code for code, name in country_options],
            format_func=lambda x: dict(country_options)[x],
            index=0
        )
        
        address = st.text_input("Enter an address:")
        
        if st.button("Get Coordinates"):
            if address:
                with st.spinner("Getting coordinates..."):
                    result = get_coordinates(address, selected_country, api_key)
                
                if result:
                    st.success("Location found!")
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Latitude", f"{result['latitude']:.6f}")
                    with col2:
                        st.metric("Longitude", f"{result['longitude']:.6f}")
                    with col3:
                        st.metric("Confidence", result['confidence'])
                    st.write("**Original Address:**")
                    st.text(result['original_address'])
                    st.write("**Matched Address:**")
                    st.text(result['address'])
                    st.write(f"**Match Level:** {result['match_level']}")
                else:
                    st.error("Could not find location. Please try a different address.")
    
    # CSV File Tab
    with tab2:
        st.header("Process CSV File")
        st.write("Upload a CSV file containing addresses to process in batch.")
        
        # Country selection for CSV processing
        selected_country_csv = st.selectbox(
            "Select country for CSV processing (or Global for no filter):",
            options=[code for code, name in country_options],
            format_func=lambda x: dict(country_options)[x],
            index=0,
            key="csv_country"
        )
        
        uploaded_file = st.file_uploader("Choose a CSV file", type="csv")
        
        if uploaded_file is not None:
            # Read CSV
            df = pd.read_csv(uploaded_file)
            
            # Show column selection
            st.write("Preview of uploaded data:")
            st.dataframe(df.head())
            
            # Select address column
            address_column = st.selectbox(
                "Select the column containing addresses:",
                options=df.columns
            )
            
            if st.button("Process CSV"):
                with st.spinner("Processing addresses..."):
                    result_df = process_csv(df.copy(), address_column, selected_country_csv, api_key)
                    
                    # Create download button for results
                    st.success("Processing complete! You can now download the results.")
                    
                    # Show results preview
                    st.write("Preview of results:")
                    st.dataframe(result_df.head())
                    
                    # Convert dataframe to CSV for download
                    csv = result_df.to_csv(index=False)
                    st.download_button(
                        label="Download Results",
                        data=csv,
                        file_name="geocoded_results.csv",
                        mime="text/csv"
                    )

if __name__ == "__main__":
    main()
