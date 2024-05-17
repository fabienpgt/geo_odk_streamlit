import streamlit as st
import pandas as pd
import geopandas as gpd
from shapely.geometry import LineString
import os
import folium
from streamlit_folium import st_folium

# Fonction pour transformer les données GPS en WKT
def gps_to_wkt(coordinates):
    line = LineString(coordinates)
    return line.wkt

# Fonction pour convertir les données en GeoDataFrame
def convert_to_gdf(df, gps_col):
    def parse_coordinates(coord_string):
        # Inverser latitude et longitude
        coords = [tuple(map(float, coord.split()[:2]))[::-1] for coord in coord_string.split(';') if len(coord.split()) >= 2]
        return coords

    df = df.dropna(subset=[gps_col])  # Filtrer les valeurs NaN
    df[gps_col] = df[gps_col].apply(parse_coordinates)
    df['geometry'] = df[gps_col].apply(LineString)
    gdf = gpd.GeoDataFrame(df, geometry='geometry')
    gdf = gdf.drop(columns=[gps_col])  # Supprimer la colonne contenant les listes
    return gdf

# Interface utilisateur Streamlit
st.title("Transformation de données GPS en WKT (Lignes)")

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
            st.write("Aperçu des données sélectionnées:")
            st.write(df[[gps_col]].head())

            format_option = st.selectbox("Choisissez le format de sortie", ["shapefile", "kml", "gpkg"])

            if st.button("Convertir"):
                # Filtrer les valeurs non nulles
                df_filtered = df[df[gps_col].notnull()]

                if df_filtered.empty:
                    st.warning("La colonne sélectionnée ne contient aucune donnée GPS valide.")
                else:
                    gdf = convert_to_gdf(df_filtered, gps_col)

                    output_file = "output." + ("shp" if format_option == "shapefile" else "kml" if format_option == "kml" else "gpkg")

                    if format_option == "shapefile":
                        gdf.to_file(output_file)
                    elif format_option == "kml":
                        gdf.to_file(output_file, driver='KML')
                    elif format_option == "gpkg":
                        gdf.to_file(output_file, driver='GPKG')

                    st.success(f"Fichier {output_file} créé avec succès.")
                    with open(output_file, "rb") as file:
                        st.download_button(label="Télécharger le fichier", data=file, file_name=output_file)
                    
                    # Supprimer le fichier après téléchargement
                    os.remove(output_file)
