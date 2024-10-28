import streamlit as st
import pandas as pd
import fiona
import geopandas as gpd
from shapely.geometry import LineString, Point, Polygon
import os
import zipfile
import tempfile

# Enable the KML driver for reading and writing
fiona.supported_drivers['KML'] = 'rw'

# Function to determine the geometry type based on a sample of coordinates
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

# Function to convert data into a GeoDataFrame with selected columns
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

    # Create the geometry column
    df['geometry'] = df[gps_col].apply(lambda coord_string: create_geometry(parse_and_validate_coordinates(coord_string)[0]))
    
    # Keep only the selected columns
    gdf = gpd.GeoDataFrame(df[selected_columns + ['geometry']], geometry='geometry')
    return gdf

# Streamlit user interface
st.title("ODK Spatial Data Transformer")
st.subheader("Convert ODK Spatial Data to Geospatial Format")

uploaded_file = st.file_uploader("Choose an Excel file", type=["xlsx"])

if uploaded_file:
    xls = pd.ExcelFile(uploaded_file)
    sheet_names = xls.sheet_names
    sheet_name = st.selectbox("Choose the sheet", sheet_names)

    if sheet_name:
        df = pd.read_excel(uploaded_file, sheet_name=sheet_name)
        
        columns = df.columns.tolist()
        gps_col = st.selectbox("Choose the column containing GPS data", columns)

        if gps_col:
            # Validate the selected column
            sample_coords, geometry_type = parse_and_validate_coordinates(df[gps_col].iloc[0])

            if geometry_type == "Invalid":
                st.warning("The selected column does not contain valid GPS data for a geometry.")
            else:
                st.write(f"Detected geometry type for the column: {geometry_type}")

                # Use radio buttons for geometry transformation choice (for polygons only)
                if geometry_type == "Polygon":
                    transformation = st.radio("Choose the geometry transformation", ["line", "polygon"])
                else:
                    transformation = geometry_type.lower()  # Automatically set for Point and Line

                # Select columns to include in geospatial data
                selected_columns = st.multiselect("Select columns to include in the export", columns, default=[gps_col])

                # Use radio buttons for output format
                format_option = st.radio("Choose the output format", ["shapefile", "kml", "gpkg", "geoparquet", "geojson"])

                if st.button("Convert"):
                    # Filter non-null values
                    df_filtered = df[df[gps_col].notnull()]

                    if df_filtered.empty:
                        st.warning("The selected column does not contain any valid GPS data.")
                    else:
                        gdf = convert_to_gdf(df_filtered, gps_col, transformation, geometry_type, selected_columns)
                        
                        # Use a temporary file for output
                        with tempfile.TemporaryDirectory() as tmpdirname:
                            final_geometry_type = transformation if geometry_type == "Polygon" else geometry_type.lower()
                            output_file_base = os.path.join(tmpdirname, f"{sheet_name}_{gps_col}_{final_geometry_type}")

                            # Save according to the selected format
                            if format_option == "shapefile":
                                # Create a zip archive for the shapefile
                                gdf.to_file(f"{output_file_base}.shp")
                                zip_filename = f"{output_file_base}.zip"
                                with zipfile.ZipFile(zip_filename, 'w') as zipf:
                                    for ext in ['shp', 'shx', 'dbf', 'prj', 'cpg']:
                                        file = f"{output_file_base}.{ext}"
                                        if os.path.exists(file):
                                            zipf.write(file, os.path.basename(file))

                                output_file = zip_filename
                            elif format_option == "kml":
                                output_file = f"{output_file_base}.kml"
                                gdf.to_file(output_file, driver='KML')
                            elif format_option == "gpkg":
                                output_file = f"{output_file_base}.gpkg"
                                gdf.to_file(output_file, driver='GPKG')
                            elif format_option == "geoparquet":
                                output_file = f"{output_file_base}.parquet"
                                gdf.to_parquet(output_file)
                            elif format_option == "geojson":
                                output_file = f"{output_file_base}.geojson"
                                gdf.to_file(output_file, driver='GeoJSON')

                            # Download the file and automatically delete it afterward
                            st.success(f"File {os.path.basename(output_file)} created successfully.")
                            with open(output_file, "rb") as file:
                                st.download_button(label="Download the file", data=file, file_name=os.path.basename(output_file))
