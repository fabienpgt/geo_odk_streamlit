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

# App Title and Introduction
st.title("ODK Spatial Data Transformer 🌍")
st.markdown("Transform ODK spatial data into a geospatial format of your choice. Upload an Excel file with GPS coordinates, select transformation options, and export as shapefile, KML, GPKG, and more!")

# Sidebar for Input and Configuration
with st.sidebar:
    st.header("Configuration")
    uploaded_file = st.file_uploader("Upload Excel file", type=["xlsx"], help="Upload an Excel file containing GPS data.")

# Determine Geometry Type Function
def determine_geometry_type(coords):
    if len(coords) == 1:
        return "Point"
    elif len(coords) >= 2 and coords[0] != coords[-1]:
        return "Line"
    elif len(coords) >= 4 and coords[0] == coords[-1]:
        return "Polygon"
    return "Unknown"

# Parse Coordinates Function
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

# Convert to GeoDataFrame
def convert_to_gdf(df, gps_col, transformation, geometry_type, selected_columns):
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

    df['geometry'] = df[gps_col].apply(lambda coord_string: create_geometry(parse_and_validate_coordinates(coord_string)[0]))
    gdf = gpd.GeoDataFrame(df[selected_columns + ['geometry']], geometry='geometry')
    return gdf

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
            sample_coords, geometry_type = parse_and_validate_coordinates(df[gps_col].iloc[0])
            
            if geometry_type == "Invalid":
                st.warning("The selected column does not contain valid GPS data.")
            else:
                st.write(f"Detected geometry type: **{geometry_type}**")
                
                if geometry_type == "Polygon":
                    transformation = st.radio("Geometry Transformation", ["line", "polygon"], index=1)
                else:
                    transformation = geometry_type.lower()

                selected_columns = st.multiselect("Select Columns to Include", columns, default=[gps_col])
                format_option = st.radio("Output Format", ["shapefile", "kml", "gpkg", "geoparquet", "geojson"], index=4)
                
                if st.button("Convert Data"):
                    st.info("Processing your data... 📊")
                    df_filtered = df[df[gps_col].notnull()]
                    
                    if df_filtered.empty:
                        st.warning("No valid GPS data found.")
                    else:
                        gdf = convert_to_gdf(df_filtered, gps_col, transformation, geometry_type, selected_columns)
                        
                        with tempfile.TemporaryDirectory() as tmpdirname:
                            output_base = os.path.join(tmpdirname, f"{sheet_name}_{gps_col}_{transformation}")
                            output_file = ""

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
                                gdf.to_parque
