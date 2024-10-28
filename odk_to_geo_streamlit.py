import streamlit as st
import pandas as pd
import fiona
import geopandas as gpd
from shapely.geometry import LineString, Point, Polygon
import os
import zipfile
import tempfile

# Activer le driver KML pour lecture et écriture
fiona.supported_drivers['KML'] = 'rw'

# Fonction pour déterminer le type de géométrie en fonction d'un échantillon de coordonnées
def determine_geometry_type(coords):
    if len(coords) == 1:
        return "Point"
    elif len(coords) >= 2 and coords[0] != coords[-1]:
        return "Line"
    elif len(coords) >= 4 and coords[0] == coords[-1]:
        return "Polygon"
    return "Unknown"

# Fonction pour analyser et valider les coordonnées
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

# Fonction pour convertir les données en GeoDataFrame avec les colonnes sélectionnées
def convert_to_gdf(df, gps_col, transformation, geometry_type, selected_columns):
    # Convertir les colonnes datetime en chaînes de caractères
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

    # Créer la colonne de géométrie
    df['geometry'] = df[gps_col].apply(lambda coord_string: create_geometry(parse_and_validate_coordinates(coord_string)[0]))
    
    # Garder uniquement les colonnes sélectionnées
    gdf = gpd.GeoDataFrame(df[selected_columns + ['geometry']], geometry='geometry')
    return gdf

# Interface utilisateur Streamlit
st.title("Transformation de données GPS en WKT")

uploaded_file = st.file_uploader("Choisissez un fichier Excel", type=["xlsx"])

if uploaded_file:
    xls = pd.ExcelFile(uploaded_file)
    sheet_names = xls.sheet_names
    sheet_name = st.selectbox("Choisissez la feuille", sheet_names)

    if sheet_name:
        df = pd.read_excel(uploaded_file, sheet_name=sheet_name)
        
        columns = df.columns.tolist()
        gps_col = st.selectbox("Choisissez la colonne contenant les données GPS", columns)

        if gps_col:
            # Validation de la colonne sélectionnée
            sample_coords, geometry_type = parse_and_validate_coordinates(df[gps_col].iloc[0])

            if geometry_type == "Invalid":
                st.warning("La colonne sélectionnée ne contient pas de données GPS valides pour une géométrie.")
            else:
                st.write(f"Type de géométrie détecté pour la colonne : {geometry_type}")

                # Utiliser des boutons radio pour le choix de transformation de la géométrie (uniquement pour les polygones)
                if geometry_type == "Polygon":
                    transformation = st.radio("Choisissez la transformation de géométrie", ["line", "polygon"])
                else:
                    transformation = geometry_type.lower()  # Automatiquement défini pour Point et Line

                # Sélection des colonnes à inclure dans les données géospatiales
                selected_columns = st.multiselect("Sélectionnez les colonnes à inclure dans l'exportation", columns, default=[gps_col])

                # Utiliser des boutons radio pour le format de sortie
                format_option = st.radio("Choisissez le format de sortie", ["shapefile", "kml", "gpkg", "geoparquet", "geojson"])

                if st.button("Convertir"):
                    # Filtrer les valeurs non nulles
                    df_filtered = df[df[gps_col].notnull()]

                    if df_filtered.empty:
                        st.warning("La colonne sélectionnée ne contient aucune donnée GPS valide.")
                    else:
                        gdf = convert_to_gdf(df_filtered, gps_col, transformation, geometry_type, selected_columns)
                        
                        # Utilisation d'un fichier temporaire pour la sortie
                        with tempfile.TemporaryDirectory() as tmpdirname:
                            final_geometry_type = transformation if geometry_type == "Polygon" else geometry_type.lower()
                            output_file_base = os.path.join(tmpdirname, f"{sheet_name}_{gps_col}_{final_geometry_type}")

                            # Sauvegarder selon le format sélectionné
                            if format_option == "shapefile":
                                # Créer une archive zip pour le shapefile
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

                            # Télécharger le fichier et le supprimer automatiquement après
                            st.success(f"Fichier {os.path.basename(output_file)} créé avec succès.")
                            with open(output_file, "rb") as file:
                                st.download_button(label="Télécharger le fichier", data=file, file_name=os.path.basename(output_file))
