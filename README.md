# ODK Spatial Data Transformer 🌍

Transform ODK spatial data into a geospatial format.



## Requirements

Before you start, make sure you have the following installed on your machine:

- **Python 3.11** or higher
- **Poetry** for dependency management and virtuak environment handling


## Features

- Upload Excel or CSV files containing GPS data.
- Select specific sheets (for Excel files) and specify delimiters (for CSV files).
- Choose the GPS column and set transformation options for polygons.
- Export data in various geospatial formats: Shapefile, KML, GeoPackage, GeoParquet, and GeoJSON.
- Download the converted file directly from the app.


## Setup

1. Clone the Repository
2. Run 'poetry install'
3. Run 'poetry run streamlit run .\odk_to_geo_streamlit.py' to launch the app