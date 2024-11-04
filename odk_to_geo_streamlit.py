import streamlit as st
import pandas as pd
import geopandas as gpd
import tempfile
import zipfile
import os
from shapely.geometry import LineString, Point, Polygon
import fiona

# Enable KML driver for reading and writing
fiona.supported_drivers['KML'] = 'rw'

# Function to determine geometry type based on sample coordinates
def determine_geometry_type(coords):
    if len(coords) == 1:
        return "Point"
    elif len(coords) >= 2 and coords[0] != coords[-1]:
        return "Line"
    elif len(coords) >= 4 and coords[0] == coords[-1]:
        return "Polygon"
    return "Unknown"

# Function to parse and validate coordinates
def parse_and_validate_coordinates(coord_string):
    if isinstance(coord_string, str):
        try:
            coords = [
                tuple(map(float, coord.split()[:2]))[::-1] 
                for coord in coord_string.split(';') 
                if len(coord.split()) >= 2
            ]
            geometry_type = determine_geometry_type(coords)
            return coords, geometry_type
        except ValueError:
            return [], "Invalid"
    else:
        return [], "Invalid"

# Function to convert data to GeoDataFrame
def convert_to_gdf(df, gps_col, transformation, geometry_type, selected_columns):
    # Convert datetime columns to strings
    for col in selected_columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            df[col] = df[col].astype(str)

    def create_geometry(coords):
        if geometry_type == "Point":
            return Point(coords[0])
        elif geometry_type == "Line" or (geometry_type == "Polygon" and transformation == "line"):
            return LineString(coords)
        elif geometry_type == "Polygon" and transformation == "polygon":
            return Polygon(coords)
        return None

    # Create geometry column based on coordinates
    df['geometry'] = df[gps_col].apply(lambda coord_string: create_geometry(parse_and_validate_coordinates(coord_string)[0]))
    
    # Return GeoDataFrame with selected columns
    gdf = gpd.GeoDataFrame(df[selected_columns + ['geometry']], geometry='geometry')

    # Set CRS to epsg 4326
    gdf.set_crs(epsg=4326, inplace=True)
    
    return gdf

# App Title and Introduction
st.title("ODK Spatial Data Transformer 🌍")
st.markdown("Transform ODK spatial data into a geospatial format of your choice.")

# Steps Overview for the User
st.markdown("""
### How to Use This App

1. **Upload Your Data**: Use the sidebar to upload your Excel file with GPS data.
2. **Select Sheet and GPS Column**: Choose the sheet and GPS column containing your location data.
3. **Set Transformation Options**: If your data represents polygons, choose if you want to convert them to lines or polygons.
4. **Choose Export Format**: Select the format you want for your geospatial output (e.g., GeoJSON, KML).
5. **Convert and Download**: Click 'Convert Data' to process your file and download the output.
""")

# Sidebar for Input and Configuration
with st.sidebar:
    st.header("Configuration")
    uploaded_file = st.file_uploader("Upload Excel file", type=["xlsx"], help="Upload an Excel file containing GPS data.")

# Main App Logic
if uploaded_file:
    xls = pd.ExcelFile(uploaded_file)
    sheet_names = xls.sheet_names
    sheet_name = st.selectbox("Select Sheet", sheet_names)
    
    if sheet_name:
        df = pd.read_excel(uploaded_file, sheet_name=sheet_name)
        columns = df.columns.tolist()
        gps_col = st.selectbox("Select GPS Column", columns)
        
        if gps_col:
            if gps_col == 'geometry' :
                df = df.rename(columns={gps_col: f"{gps_col}_text"}, errors="raise")
                gps_col = f"{gps_col}_text"

                for i, item in enumerate(columns):
                	if item == gps_col:
                		mylist[i] = f"{gps_col}_text"

            st.write(columns)
                
                
            sample_coords, geometry_type = parse_and_validate_coordinates(df[gps_col].iloc[0])
            
            if geometry_type == "Invalid":
                st.warning("The selected column does not contain valid GPS data.")
            else:
                st.write(f"Detected geometry type: **{geometry_type}**")
                
                # Geometry transformation choice (only for polygons)
                if geometry_type == "Polygon":
                    transformation = st.radio("Geometry Transformation", ["line", "polygon"], index=1)
                else:
                    transformation = geometry_type.lower()

                # Checkbox to select all columns
                select_all = st.checkbox("Select All Columns", value=False, help="Check to include all columns in the export.")
                
                # Multiselect for individual column selection
                selected_columns = st.multiselect(
                    "Select Columns to Include in Export", 
                    columns, 
                    default=columns if select_all else [gps_col],
                    help="Choose additional fields to include in the output geospatial file."
                )

                # Select output format
                format_option = st.radio("Output Format", ["shapefile", "kml", "gpkg", "geoparquet", "geojson"], index=4)
                
                # Convert and Export button
                if st.button("Convert Data"):
                    df_filtered = df[df[gps_col].notnull()]
                    
                    if df_filtered.empty:
                        st.warning("No valid GPS data found.")
                    else:
                        gdf = convert_to_gdf(df_filtered, gps_col, transformation, geometry_type, selected_columns)
                        
                        with tempfile.TemporaryDirectory() as tmpdirname:
                            output_base = os.path.join(tmpdirname, f"{sheet_name}_{gps_col}_{transformation}")
                            output_file = ""

                            # Save based on selected format
                            if format_option == "shapefile":
                                gdf.to_file(f"{output_base}.shp")
                                zip_filename = f"{output_base}.zip"
                                with zipfile.ZipFile(zip_filename, 'w') as zipf:
                                    for ext in ['shp', 'shx', 'dbf', 'prj', 'cpg']:
                                        file = f"{output_base}.{ext}"
                                        if os.path.exists(file):
                                            zipf.write(file, os.path.basename(file))
                                output_file = zip_filename
                            elif format_option == "kml":
                                output_file = f"{output_base}.kml"
                                gdf.to_file(output_file, driver='KML')
                            elif format_option == "gpkg":
                                output_file = f"{output_base}.gpkg"
                                gdf.to_file(output_file, driver='GPKG')
                            elif format_option == "geoparquet":
                                output_file = f"{output_base}.parquet"
                                gdf.to_parquet(output_file)
                            elif format_option == "geojson":
                                output_file = f"{output_base}.geojson"
                                gdf.to_file(output_file, driver='GeoJSON')

                            st.success("File created successfully! 🎉")
                            # Download the file and delete afterward
                            with open(output_file, "rb") as file:
                                st.download_button(
                                    label="📥 Download File", 
                                    data=file, 
                                    file_name=os.path.basename(output_file)
                                )
