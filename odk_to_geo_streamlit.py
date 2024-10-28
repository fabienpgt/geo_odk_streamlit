import streamlit
import tempfile
import zipfile
import os
from shapely.geometry import LineString, Point, Polygon
import fiona
import pandas
import geopandas

# Enable KML driver for reading and writing
fiona.supported_drivers['KML'] = 'rw'

# App Title and Introduction
st.title("ODK Spatial Data Transformer 🌍")
st.markdown("Transform ODK spatial data into a geospatial format of your choice. Upload an Excel file with GPS coordinates, select transformation options, and export as shapefile, KML, GPKG, and more!")

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
                    st.info("Processing your data... 📊")
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
                            
                            # Download the file and delete afterward
                            st.success("File created successfully! 🎉")
                            with open(output_file, "rb") as file:
                                st.download_button(
                                    label="📥 Download File", 
                                    data=file, 
                                    file_name=os.path.basename(output_file)
                                )
